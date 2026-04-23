Calculate Formation Energy Per Atom
===================================

Purpose
-------

This workflow explains how ``scripts/calc_formation.py`` calculates formation
energies per atom for Fe-Co-S structures stored under a common directory such as
``~/Downloads/FeCoS``.

The script reads total energies for target structures from a CSV file, reads
elemental reference energies from separate pure-element VASP calculations, and
appends composition counts plus formation energy per atom back to the same CSV.

Inputs
------

The script expects this directory layout:

.. code-block:: text

   ~/Downloads/FeCoS/
   |-- FeCoS_energies.csv
   |-- Fe/
   |   |-- OUTCAR
   |   `-- CONTCAR
   |-- Co/
   |   |-- OUTCAR
   |   `-- CONTCAR
   |-- S/
   |   |-- OUTCAR
   |   `-- CONTCAR
   |-- pos_1/
   |   |-- OUTCAR
   |   `-- CONTCAR
   `-- ...

CSV contract
------------

The CSV file must contain at least these columns:

``folder``
  A human-readable identifier such as ``pos_1``.

``energy``
  The total energy of the structure in eV.

``outcar_path``
  Absolute or relative path to the structure's ``OUTCAR``. The script uses the
  parent directory of this path to locate the sibling ``CONTCAR``.

Reference data contract
-----------------------

For each reference element in ``['Fe', 'Co', 'S']``, the script expects:

- ``<base_dir>/<element>/OUTCAR`` containing the elemental total energy.
- ``<base_dir>/<element>/CONTCAR`` containing the elemental structure.

The elemental ``OUTCAR`` is parsed for the final free energy.

The elemental ``CONTCAR`` is parsed to count how many atoms of that element are
present. The script normalizes parser keys to plain strings such as ``Fe`` and
``Co`` before using them in lookups.

Procedure
---------

1. Read ``FeCoS_energies.csv`` into a pandas DataFrame.
2. For each pure-element reference folder ``Fe``, ``Co``, and ``S``:

   - parse the final free energy from ``OUTCAR``
   - parse the composition from ``CONTCAR``
   - divide the total elemental energy by the number of elemental atoms in that
     ``CONTCAR`` to obtain a reference energy per atom

3. Abort if any elemental reference energy is missing.
4. For each material row in the CSV:

   - read the row's ``energy`` as the total energy in eV
   - locate ``CONTCAR`` next to ``outcar_path``
   - count ``Fe``, ``Co``, and ``S`` atoms from that ``CONTCAR``
   - compute formation energy per atom using the reference energies

5. Append the derived columns to the DataFrame and overwrite the original CSV.

Formula
-------

The script uses the formation-energy-per-atom definition implemented in
``vasp_wfl.formation.Compound``:

.. math::

   E_f = \frac{E_{\mathrm{total}} - \sum_i n_i E_i^{\mathrm{ref}}}{\sum_i n_i}

where:

- :math:`E_f` is the formation energy per atom in eV/atom
- :math:`E_{\mathrm{total}}` is the compound total energy in eV
- :math:`n_i` is the atom count for element :math:`i`
- :math:`E_i^{\mathrm{ref}}` is the pure-element reference energy per atom in eV/atom

This means the output column ``formation_energy`` is a per-atom quantity.

Outputs
-------

The script overwrites the input CSV and appends these columns:

``num_Fe``
  Number of Fe atoms parsed from the row's ``CONTCAR``.

``num_Co``
  Number of Co atoms parsed from the row's ``CONTCAR``.

``num_S``
  Number of S atoms parsed from the row's ``CONTCAR``.

``formation_energy``
  Formation energy per atom in eV/atom.

What Is Not Written
-------------------

The elemental reference energies from the ``Fe``, ``Co``, and ``S`` folders are
not appended as CSV columns. They are only stored in memory while the script is
running.

Failure Modes
-------------

Common reasons for failure are:

- ``FeCoS_energies.csv`` is missing.
- A reference ``OUTCAR`` or ``CONTCAR`` is missing for ``Fe``, ``Co``, or ``S``.
- A reference ``OUTCAR`` cannot be parsed into a final free energy.
- A material row points to an ``OUTCAR`` whose sibling ``CONTCAR`` is missing or malformed.
- Element keys are inconsistent between structure parsing and the reference-energy dictionary.

Current implementation avoids the last issue by converting parsed element/species
keys to plain strings before composition lookup and formation-energy calculation.

Practical Notes For Future LLMs
-------------------------------

- Treat the CSV ``energy`` column as the compound total energy in eV, not per atom.
- Treat ``formation_energy`` as eV/atom.
- If you adapt this script to another chemical system, update both the
  ``elements`` list and the expected reference folders.
- If you run the script, remember that it overwrites the original CSV in place.
