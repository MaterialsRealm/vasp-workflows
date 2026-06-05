"""Plot Mn-Bi-O DFT formation energies against two model predictions."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def expand_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def compound_rows(df: pd.DataFrame) -> pd.DataFrame:
    n_elements = (df[["n_Mn", "n_Bi", "n_O"]] > 0).sum(axis=1)
    return df[n_elements > 1].copy()


def read_model_table(path: Path, label: str) -> pd.DataFrame:
    df = compound_rows(pd.read_csv(path))
    required = {
        "ID",
        "dft_formation_energy_per_atom",
        "model_formation_energy_per_atom",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path} is missing columns: {sorted(missing)}")
    if df["ID"].duplicated().any():
        duplicates = df[df["ID"].duplicated(keep=False)]["ID"].tolist()
        raise ValueError(f"{path} has duplicate IDs: {duplicates}")

    return df[
        [
            "ID",
            "dft_formation_energy_per_atom",
            "model_formation_energy_per_atom",
        ]
    ].rename(columns={"model_formation_energy_per_atom": f"{label}_formation_energy_per_atom"})


def metrics(dft: pd.Series, pred: pd.Series) -> dict[str, float]:
    error = pred - dft
    if len(dft) < 2 or np.std(dft) == 0 or np.std(pred) == 0:
        pearson_r = float("nan")
    else:
        pearson_r = float(np.corrcoef(dft, pred)[0, 1])
    return {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "max_abs": float(np.max(np.abs(error))),
        "pearson_r": pearson_r,
    }


def build_combined_table(args: argparse.Namespace) -> pd.DataFrame:
    my_label = args.my_label
    xie_label = args.xie_label
    my = read_model_table(expand_path(args.my_csv), my_label)
    xie = read_model_table(expand_path(args.xie_csv), xie_label)

    merged = my.merge(
        xie,
        on=["ID", "dft_formation_energy_per_atom"],
        how="inner",
        validate="one_to_one",
    )
    missing_my = sorted(set(xie["ID"]) - set(my["ID"]))
    missing_xie = sorted(set(my["ID"]) - set(xie["ID"]))
    if missing_my or missing_xie:
        raise ValueError(f"Unmatched IDs. missing_my={missing_my}, missing_xie={missing_xie}")

    for label in [my_label, xie_label]:
        pred_col = f"{label}_formation_energy_per_atom"
        merged[f"{label}_error_per_atom"] = merged[pred_col] - merged["dft_formation_energy_per_atom"]
        merged[f"{label}_absolute_error_per_atom"] = merged[f"{label}_error_per_atom"].abs()

    return merged.sort_values("ID").reset_index(drop=True)


def plot_comparison(df: pd.DataFrame, args: argparse.Namespace) -> dict[str, dict[str, float]]:
    my_label = args.my_label
    xie_label = args.xie_label
    output_png = expand_path(args.output_png)
    output_png.parent.mkdir(parents=True, exist_ok=True)

    dft = df["dft_formation_energy_per_atom"]
    metric_by_model = {
        my_label: metrics(dft, df[f"{my_label}_formation_energy_per_atom"]),
        xie_label: metrics(dft, df[f"{xie_label}_formation_energy_per_atom"]),
    }

    values = [
        dft.to_numpy(dtype=float),
        df[f"{my_label}_formation_energy_per_atom"].to_numpy(dtype=float),
        df[f"{xie_label}_formation_energy_per_atom"].to_numpy(dtype=float),
    ]
    lower = min(float(v.min()) for v in values)
    upper = max(float(v.max()) for v in values)
    padding = max((upper - lower) * 0.06, 0.05)
    axis_range = [lower - padding, upper + padding]

    fig, ax = plt.subplots(figsize=(8.8, 8.8), constrained_layout=True)
    colors = {my_label: "#2563eb", xie_label: "#dc2626"}
    for label in [my_label, xie_label]:
        m = metric_by_model[label]
        ax.scatter(
            dft,
            df[f"{label}_formation_energy_per_atom"],
            label=f"{label} (MAE={m['mae']:.3f}, r={m['pearson_r']:.3f})",
            s=58,
            alpha=0.86,
            edgecolors="white",
            linewidths=0.7,
            color=colors[label],
        )

    ax.plot(axis_range, axis_range, linestyle="--", color="#0f172a", linewidth=1.2, label="ideal")
    ax.set_xlim(axis_range)
    ax.set_ylim(axis_range)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("DFT formation energy (eV/atom)")
    ax.set_ylabel("Model formation energy (eV/atom)")
    ax.set_title("Mn-Bi-O Compound Formation Energy Prediction Comparison")
    ax.grid(True, color="#e2e8f0")
    ax.legend(frameon=True)
    fig.savefig(output_png, dpi=220)
    plt.close(fig)
    return metric_by_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot my model and Xie's model on one Mn-Bi-O parity plot.")
    parser.add_argument(
        "--my-csv",
        default="~/Library/CloudStorage/CloudMounter-StampedeWork/run/MnBiO/predict/my new/MnBiO_dft_vs_model_formation_energies.csv",
    )
    parser.add_argument(
        "--xie-csv",
        default="~/Library/CloudStorage/CloudMounter-StampedeWork/run/MnBiO/predict/xie old/MnBiO_dft_vs_model_formation_energies.csv",
    )
    parser.add_argument("--my-label", default="my_new")
    parser.add_argument("--xie-label", default="xie_old")
    parser.add_argument(
        "--output-csv",
        default="~/Library/CloudStorage/CloudMounter-StampedeWork/run/MnBiO/predict/MnBiO_model_comparison.csv",
    )
    parser.add_argument(
        "--output-png",
        default="~/Library/CloudStorage/CloudMounter-StampedeWork/run/MnBiO/predict/MnBiO_model_comparison.png",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = build_combined_table(args)
    for column in df.columns:
        if column.endswith("_per_atom") and not df[column].apply(math.isfinite).all():
            raise ValueError(f"{column} contains non-finite values")

    output_csv = expand_path(args.output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv, index=False, float_format="%.17g")
    metric_by_model = plot_comparison(df, args)

    print(f"Wrote combined CSV: {output_csv}")
    print(f"Wrote combined plot: {expand_path(args.output_png)}")
    print(f"Compared rows: {len(df)}")
    for label, m in metric_by_model.items():
        print(
            f"{label}: MAE={m['mae']:.8f} eV/atom, "
            f"RMSE={m['rmse']:.8f} eV/atom, "
            f"max_abs={m['max_abs']:.8f} eV/atom, "
            f"pearson_r={m['pearson_r']:.8f}",
        )


if __name__ == "__main__":
    main()
