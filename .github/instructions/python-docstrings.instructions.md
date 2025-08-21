---
description: "Standards for writing Python docstrings."
applyTo: '**/*.py'
---

# Python Docstrings Standards

## Rules

### Use imperative mood

PEP 257 recommends that the first line of a docstring be written in the imperative mood,
for consistency. To write the docstring in the imperative, phrase the first line as if it
were a command.

```python
def average(values: list[float]) -> float:
    """Returns the mean of the given values."""
```

Use instead:

```python
def average(values: list[float]) -> float:
    """Return the mean of the given values."""
```
