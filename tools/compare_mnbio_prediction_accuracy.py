"""Join Mn-Bi-O DFT formation energies with model predictions and plot parity."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go


REQUIRED_DFT_COLUMNS = {
    "ID",
    "DFT_raw_energy",
    "n_Mn",
    "n_Bi",
    "n_O",
    "num_atoms",
    "formation_energy",
}


def expand_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def relative_to_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def read_prediction_csv(
    csv_path: Path,
    predict_root: Path,
    cif_dir: Path | None = None,
    source_group: str | None = None,
    require_cifs: bool = True,
) -> pd.DataFrame:
    raw = pd.read_csv(csv_path, header=None)
    if raw.shape[1] < 2:
        raise ValueError(f"Prediction CSV must have at least two columns: {csv_path}")

    first_id = str(raw.iloc[0, 0]).strip().lower()
    first_value = str(raw.iloc[0, 1]).strip().lower()
    if first_id == "id" and first_value in {"inference", "prediction", "formation_energy"}:
        raw = raw.iloc[1:].reset_index(drop=True)

    df = raw.iloc[:, :2].copy()
    df.columns = ["ID", "model_formation_energy_per_atom"]
    df["ID"] = df["ID"].astype(str)
    df["model_formation_energy_per_atom"] = pd.to_numeric(
        df["model_formation_energy_per_atom"],
        errors="raise",
    )

    if source_group is None:
        source_group = relative_to_or_absolute(csv_path.parent, predict_root)
    if cif_dir is None:
        cif_dir = csv_path.parent

    df["source_group"] = source_group
    df["source_csv"] = relative_to_or_absolute(csv_path, predict_root)
    df["cif_path"] = [cif_dir / f"{material_id}.cif" for material_id in df["ID"]]

    missing_cifs = [path for path in df["cif_path"] if not path.exists()]
    if missing_cifs and require_cifs:
        formatted = "\n".join(str(path) for path in missing_cifs)
        raise FileNotFoundError(f"Missing CIF files for prediction rows:\n{formatted}")

    return df


def read_all_predictions(args: argparse.Namespace) -> pd.DataFrame:
    predict_root = expand_path(args.predict_root)
    if args.prediction_csv is not None:
        return read_prediction_csv(
            expand_path(args.prediction_csv),
            predict_root,
            cif_dir=expand_path(args.cif_dir) if args.cif_dir is not None else None,
            source_group=args.source_group,
            require_cifs=not args.allow_missing_cifs,
        )

    csv_paths = sorted(path for path in predict_root.rglob("*.csv") if path.name == "results.csv")
    if not csv_paths:
        raise FileNotFoundError(f"No results.csv files found under {predict_root}")

    predictions = pd.concat(
        [read_prediction_csv(csv_path, predict_root) for csv_path in csv_paths],
        ignore_index=True,
    )

    duplicated = predictions[predictions["ID"].duplicated(keep=False)]
    if not duplicated.empty:
        raise ValueError(f"Duplicate predicted IDs found:\n{duplicated[['ID', 'source_csv']].to_string(index=False)}")

    return predictions


def read_dft_formation_energies(energies_csv: Path) -> pd.DataFrame:
    dft = pd.read_csv(energies_csv)
    missing = REQUIRED_DFT_COLUMNS - set(dft.columns)
    if missing:
        raise ValueError(f"DFT CSV is missing required columns: {sorted(missing)}")

    dft = dft.rename(columns={"formation_energy": "dft_formation_energy_per_atom"})
    dft["ID"] = dft["ID"].astype(str)

    duplicated = dft[dft["ID"].duplicated(keep=False)]
    if not duplicated.empty:
        raise ValueError(f"Duplicate DFT IDs found:\n{duplicated[['ID']].to_string(index=False)}")

    return dft


def build_accuracy_table(args: argparse.Namespace) -> pd.DataFrame:
    predict_root = expand_path(args.predict_root)
    energies_csv = expand_path(args.energies_csv)
    output_csv = expand_path(args.output_csv)

    predictions = read_all_predictions(args)
    dft = read_dft_formation_energies(energies_csv)

    missing_dft = sorted(set(predictions["ID"]) - set(dft["ID"]))
    missing_predictions = sorted(set(dft["ID"]) - set(predictions["ID"]))
    messages = []
    if missing_dft:
        messages.append(f"Predictions missing DFT rows: {missing_dft}")
    if missing_predictions and args.prediction_csv is None:
        messages.append(f"DFT rows missing predictions: {missing_predictions}")
    if messages:
        raise ValueError("\n".join(messages))

    merged = dft.merge(predictions, on="ID", how="inner", validate="one_to_one")
    merged["relative_cif_path"] = [
        relative_to_or_absolute(Path(path), predict_root) for path in merged["cif_path"]
    ]
    merged["prediction_error_per_atom"] = (
        merged["model_formation_energy_per_atom"] - merged["dft_formation_energy_per_atom"]
    )
    merged["absolute_error_per_atom"] = merged["prediction_error_per_atom"].abs()

    ordered_columns = [
        "ID",
        "source_group",
        "relative_cif_path",
        "source_csv",
        "DFT_raw_energy",
        "n_Mn",
        "n_Bi",
        "n_O",
        "num_atoms",
        "dft_formation_energy_per_atom",
        "model_formation_energy_per_atom",
        "prediction_error_per_atom",
        "absolute_error_per_atom",
    ]
    merged = merged[ordered_columns].sort_values(["source_group", "ID"]).reset_index(drop=True)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_csv, index=False, float_format="%.17g")
    return merged


def error_metrics(df: pd.DataFrame) -> dict[str, float]:
    error = df["prediction_error_per_atom"].to_numpy(dtype=float)
    dft = df["dft_formation_energy_per_atom"].to_numpy(dtype=float)
    model = df["model_formation_energy_per_atom"].to_numpy(dtype=float)
    mae = float(np.mean(np.abs(error)))
    rmse = float(np.sqrt(np.mean(error**2)))
    max_abs = float(np.max(np.abs(error)))
    if len(df) < 2 or np.std(dft) == 0 or np.std(model) == 0:
        pearson_r = float("nan")
    else:
        pearson_r = float(np.corrcoef(dft, model)[0, 1])
    return {"mae": mae, "rmse": rmse, "max_abs": max_abs, "pearson_r": pearson_r}


def make_plot(df: pd.DataFrame, args: argparse.Namespace) -> None:
    output_png = expand_path(args.output_png)
    output_html = expand_path(args.output_html) if args.output_html is not None else None
    if output_html is not None:
        output_html.parent.mkdir(parents=True, exist_ok=True)
    output_png.parent.mkdir(parents=True, exist_ok=True)

    plot_df = df[df["num_atoms"] != df[["n_Mn", "n_Bi", "n_O"]].max(axis=1)].copy()
    if plot_df.empty:
        raise ValueError("No multi-element compounds found for plotting")

    metrics = error_metrics(plot_df)
    x = plot_df["dft_formation_energy_per_atom"].to_numpy(dtype=float)
    y = plot_df["model_formation_energy_per_atom"].to_numpy(dtype=float)
    lower = float(min(x.min(), y.min()))
    upper = float(max(x.max(), y.max()))
    padding = max((upper - lower) * 0.06, 0.05)
    axis_range = [lower - padding, upper + padding]

    fig = go.Figure()
    palette = {
        "MnBiO": "#2563eb",
        "Mn+": "#dc2626",
        "Bi+": "#7c3aed",
        "O": "#059669",
    }
    for group, group_df in plot_df.groupby("source_group", sort=True):
        hover = [
            (
                f"<b>{row.ID}</b><br>"
                f"CIF: {row.relative_cif_path}<br>"
                f"DFT: {row.dft_formation_energy_per_atom:.8f} eV/atom<br>"
                f"Model: {row.model_formation_energy_per_atom:.8f} eV/atom<br>"
                f"Error: {row.prediction_error_per_atom:+.8f} eV/atom"
            )
            for row in group_df.itertuples(index=False)
        ]
        fig.add_trace(
            go.Scatter(
                x=group_df["dft_formation_energy_per_atom"],
                y=group_df["model_formation_energy_per_atom"],
                mode="markers",
                name=group,
                marker={
                    "size": 10,
                    "line": {"width": 0.8, "color": "white"},
                    "color": palette.get(group, "#334155"),
                    "opacity": 0.88,
                },
                customdata=group_df["relative_cif_path"],
                hovertext=hover,
                hoverinfo="text",
            ),
        )

    fig.add_trace(
        go.Scatter(
            x=axis_range,
            y=axis_range,
            mode="lines",
            name="ideal",
            line={"color": "#0f172a", "width": 1.4, "dash": "dash"},
            hoverinfo="skip",
        ),
    )
    fig.update_layout(
        title=(
            "Mn-Bi-O Compound Formation Energy Prediction Accuracy"
            f"<br><sup>MAE={metrics['mae']:.4f}, RMSE={metrics['rmse']:.4f}, "
            f"max |error|={metrics['max_abs']:.4f} eV/atom, Pearson r={metrics['pearson_r']:.4f}</sup>"
        ),
        template="plotly_white",
        width=880,
        height=880,
        legend={"x": 0.02, "y": 0.98, "bordercolor": "#e2e8f0", "borderwidth": 1},
        margin={"l": 80, "r": 40, "t": 95, "b": 80},
    )
    fig.update_xaxes(
        title="DFT formation energy (eV/atom)",
        range=axis_range,
        zeroline=False,
        showgrid=True,
        gridcolor="#e2e8f0",
    )
    fig.update_yaxes(
        title="Model formation energy (eV/atom)",
        range=axis_range,
        scaleanchor="x",
        scaleratio=1,
        zeroline=False,
        showgrid=True,
        gridcolor="#e2e8f0",
    )

    if output_html is not None and not args.no_html:
        div_id = "mnbio-accuracy-plot"
        plot_div = fig.to_html(full_html=False, include_plotlyjs="cdn", div_id=div_id)
        click_script = f"""
<script>
document.getElementById("{div_id}").on("plotly_click", function(data) {{
  const href = data.points && data.points[0] && data.points[0].customdata;
  if (href) {{
    window.location.href = href;
  }}
}});
</script>
"""
        output_html.write_text(
            "<!doctype html>\n"
            "<html><head><meta charset=\"utf-8\"><title>Mn-Bi-O Prediction Accuracy</title></head>"
            "<body>\n"
            f"{plot_div}\n"
            f"{click_script}\n"
            "</body></html>\n",
            encoding="utf-8",
        )

    try:
        fig.write_image(output_png)
    except Exception:
        make_matplotlib_png(plot_df, output_png, axis_range, metrics)

    print(f"Wrote accuracy CSV: {expand_path(args.output_csv)}")
    if output_html is not None and not args.no_html:
        print(f"Wrote interactive plot: {output_html}")
    print(f"Wrote static plot: {output_png}")
    print(
        f"MAE={metrics['mae']:.8f} eV/atom, "
        f"RMSE={metrics['rmse']:.8f} eV/atom, "
        f"max_abs={metrics['max_abs']:.8f} eV/atom, "
        f"pearson_r={metrics['pearson_r']:.8f}",
    )


def make_matplotlib_png(
    df: pd.DataFrame,
    output_png: Path,
    axis_range: list[float],
    metrics: dict[str, float],
) -> None:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8.8, 8.8), constrained_layout=True)
    for group, group_df in df.groupby("source_group", sort=True):
        ax.scatter(
            group_df["dft_formation_energy_per_atom"],
            group_df["model_formation_energy_per_atom"],
            label=group,
            s=48,
            alpha=0.86,
            edgecolors="white",
            linewidths=0.7,
        )
    ax.plot(axis_range, axis_range, linestyle="--", color="#0f172a", linewidth=1.2)
    ax.set_xlim(axis_range)
    ax.set_ylim(axis_range)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("DFT formation energy (eV/atom)")
    ax.set_ylabel("Model formation energy (eV/atom)")
    ax.set_title(
        "Mn-Bi-O Compound Formation Energy Prediction Accuracy\n"
        f"MAE={metrics['mae']:.4f}, RMSE={metrics['rmse']:.4f}, "
        f"max |error|={metrics['max_abs']:.4f} eV/atom, Pearson r={metrics['pearson_r']:.4f}",
    )
    ax.grid(True, color="#e2e8f0")
    ax.legend(frameon=True)
    fig.savefig(output_png, dpi=220)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare Mn-Bi-O DFT formation energies against model predictions.",
    )
    parser.add_argument(
        "--energies-csv",
        default="~/Library/CloudStorage/CloudMounter-StampedeWork/run/MnBiO/energies.csv",
        help="DFT CSV with accurate formation_energy values.",
    )
    parser.add_argument(
        "--predict-root",
        default="~/Downloads/predict",
        help="Root containing prediction results.csv files and/or CIF files.",
    )
    parser.add_argument(
        "--prediction-csv",
        default=None,
        help="Optional single prediction CSV to compare instead of scanning predict-root.",
    )
    parser.add_argument(
        "--cif-dir",
        default=None,
        help="Directory containing CIFs named {ID}.cif for --prediction-csv.",
    )
    parser.add_argument(
        "--allow-missing-cifs",
        action="store_true",
        help="Do not fail when generated CIF paths do not exist.",
    )
    parser.add_argument(
        "--source-group",
        default=None,
        help="Label to use for the prediction source when --prediction-csv is supplied.",
    )
    parser.add_argument(
        "--output-csv",
        default="~/Downloads/predict/MnBiO_dft_vs_model_formation_energies.csv",
        help="Joined output CSV.",
    )
    parser.add_argument(
        "--output-html",
        default="~/Downloads/predict/MnBiO_prediction_accuracy.html",
        help="Interactive clickable parity plot. Use --no-html to skip.",
    )
    parser.add_argument(
        "--output-png",
        default="~/Downloads/predict/MnBiO_prediction_accuracy.png",
        help="Static parity plot.",
    )
    parser.add_argument(
        "--no-html",
        action="store_true",
        help="Skip writing the interactive HTML plot.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = build_accuracy_table(args)
    if not df["dft_formation_energy_per_atom"].apply(math.isfinite).all():
        raise ValueError("At least one DFT formation energy is not finite")
    if not df["model_formation_energy_per_atom"].apply(math.isfinite).all():
        raise ValueError("At least one model formation energy is not finite")
    make_plot(df, args)


if __name__ == "__main__":
    main()
