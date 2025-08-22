---
description: "Standards for writing Python docstrings."
applyTo: '**/*.py'
---

# Python Docstrings Standards

## Rules

### Use imperative mood

The first line of a docstring be written in the imperative mood for consistency.
To write the docstring in the imperative, phrase the first line as if it were a command.

```python
def average(values: list[float]) -> float:
    """Returns the mean of the given values."""
```

Use instead:

```python
def average(values: list[float]) -> float:
    """Return the mean of the given values."""
```

### Always use triple double quotes

Use `"""` (triple double quotes) for all docstrings (modules, packages, classes, functions, methods, generators, and properties).

### One-line docstrings

Use one-liners only for obvious cases.

- Entire docstring fits on one line.
- Closing quotes are on the **same line** as the summary.
- **No blank line** before or after the docstring.
- Phrase as a command; end with a period.

```python
def cwd() -> str:
    """Return the current working directory."""
```

### Multi-line docstrings

When more detail is needed:

- First line: a short **summary** (≤ 120 characters), imperative, ends with a period.
- Then **one blank line**.
- Then the detailed description (usage, context, caveats).
- Place the closing `"""` on a **line by itself** (since it doesn’t fit on one line).
- Indentation: follow the code block’s indent; relative indentation inside the docstring is preserved.

```python
def connect(uri: str, *, timeout: float | None = None) -> Client:
    """Open a connection to the server.

    Establishes a TCP connection to the given URI and performs a handshake.
    Retries are not performed automatically.

    Args:
        uri: Server URI of the form `<scheme>://<host>:<port>`, e.g., `'tcp://localhost:5555'`.
        timeout: Optional timeout in seconds before aborting the attempt.

    Returns:
        A connected Client instance.

    Raises:
        ValueError: If the URI is malformed.
        TimeoutError: If the connection attempt times out.
        OSError: For lower-level socket errors.
    """
```

### Where docstrings are required

Provide docstrings for any function/method that is:

- Part of the **public API**,
- Of **nontrivial size**, or
- Has **non-obvious** logic or side effects.

Internal, tiny, and obvious helpers can be omitted, but err on the side of documenting.

### Do not restate the signature

Do **not** repeat parameter lists or types already visible via introspection/type hints.
Document **behavior**, side effects, constraints, and semantics.

Bad:

```python
def foo(a: int, b: int) -> int:
    """foo(a: int, b: int) -> int"""
```

Good:

```python
def foo(a: int, b: int) -> int:
    """Compute and return a stable hash of `a` and `b`."""
```

### Sections for functions/methods

When you have more than a one-line docstring, use these sections with a hanging indent of 4 spaces:

- `Args:` one entry per parameter.
- `Returns:` or `Yields:` describe the value(s) produced.
- `Raises:` list relevant exceptions (don’t list violations of the API contract).

**Types in docstrings**: only include if the function **lacks** a type annotation.

**Varargs/kwargs**: name them as `*args` and `**kwargs` in `Args:` if accepted.

**Tuple returns**: describe as a single tuple, not multiple named returns.

```python
def split_pair(s: str) -> tuple[str, str]:
    """Split the input at the first colon.

    Args:
        s: Input string in the form `"key:value"`.

    Returns:
        A tuple `(key, value)` where both elements are stripped of surrounding whitespace.

    Raises:
        ValueError: If no colon is present in the input.
    """
```

**Generators**: document what `next()` yields, not the generator object itself.

```python
def read_lines(fp: TextIO) -> Iterator[str]:
    """Yield non-empty, stripped lines from a file-like object.

    Yields:
        Each non-empty line with leading and trailing whitespace removed.
    """
```

### Side effects and mutability

Call out any side effects, external I/O, environment use, global state mutations, or in-place mutations of arguments.

```python
def normalize(v: list[float]) -> None:
    """Scale the list in place so its L2 norm is 1.0.

    Args:
        v: Sequence of floats to normalize. Modified in place.
    """
```

### Properties use noun phrases

`@property` docstrings should be attribute-style (noun phrase), not “Returns …”.

```python
class Config:
    @property
    def data_dir(self) -> Path:
        """The directory where data files are stored."""
```

### Class docstrings

- Start with what an **instance represents**, not “Class that …”.
- An `Attributes:` section for **public attributes** (no properties), following the same formatting as a function’s `Args:` section.
- Methods are documented on the methods themselves (don’t mirror the whole API in the class docstring).

```python
class SampleClass:
    """Summary of class here.

    Longer class information...
    Longer class information...

    Attributes:
        likes_spam: A boolean indicating if we like SPAM or not.
        eggs: An integer count of the eggs we have laid.
    """

    def __init__(self, likes_spam: bool = False):
        """Initializes the instance based on spam preference.

        Args:
            likes_spam: Defines if instance exhibits this preference.
        """
        self.likes_spam = likes_spam
        self.eggs = 0

    @property
    def butter_sticks(self) -> int:
        """The number of butter sticks we have."""
```

**Exceptions** (as classes) should state what the exception **represents**, not when it’s raised:

```python
# Yes:
class CheeseShopAddress:
    """The address of a cheese shop.

    ...
    """

    class OutOfCheeseError(Exception):
    """No more cheese is available."""

# No:
class CheeseShopAddress:
    """Class that describes the address of a cheese shop.

    ...
    """

class OutOfCheeseError(Exception):
    """Raised when no more cheese is available."""
```

### Inheritance and overrides

Use `@override` (from `typing_extensions` or `typing`) when a method overrides a base method.

- If behavior **does not** materially change: `@override` is sufficient; you may omit the docstring.
- If behavior **does** change or adds side effects: include a docstring describing the **differences** only.
- If you include text, be explicit about whether you **override** (replace) or **extend** (call super then add behavior).

```python
# Yes:
from typing_extensions import override

class Parent:
    def do_something(self):
        """Parent method, includes docstring."""

# Child class, method annotated with override.
class Child(Parent):
    @override
    def do_something(self):
        pass

# No:
# Child class, but without @override decorator, a docstring is required.
class Child(Parent):
    def do_something(self):
        pass

# Docstring is trivial, @override is sufficient to indicate that docs can be
# found in the base class.
class Child(Parent):
    @override
    def do_something(self):
        """See base class."""
```

### Module, package, and script docstrings

- **License**: Every file should begin with the appropriate license boilerplate (project policy).
- **Modules**: Start with a docstring describing contents/usage. Optionally summarize key exports or include a short usage example.

```python
"""A one-line summary of the module or program, terminated by a period.

Leave one blank line.  The rest of this docstring should contain an
overall description of the module or program.  Optionally, it may also
contain a brief description of exported classes and functions and/or usage
examples.

Typical usage example:

    foo = ClassFoo()
    bar = foo.function_bar()
"""
```

- **Packages** (`__init__.py`): Docstring may list exported modules/subpackages with one-line summaries.
- **Scripts**: The module docstring should double as a `-h`-style usage: purpose, syntax, environment variables, files, and options.
- **Test modules**: Module docstrings are **not required**. Add one only if it provides extra context (golden files, env setup). Avoid trivial docstrings like `"""Tests for foo.bar."""`.

```python
"""This blaze test uses golden files.

You can update those files by running
`blaze run //foo/bar:foo_test -- --update_golden_files` from the `google3`
directory.
"""
```

### Formatting details

- **Summary line**: ≤ 120 characters, imperative, ends with a period, on the same line as the opening quotes.
- **Blank lines**:
  - One-liners: **no** blank line before/after.
  - Multi-line: **one** blank line after the summary before details.
  - After a **class** docstring, leave a blank line before the first method.
- **Closing quotes**:
  - One-liners: closing quotes on the **same line** as the summary.
  - Multi-line: closing quotes on a **line by themselves**.
- **Indentation**:
  - Indent the docstring at the same level as the entity it documents.
  - Inside sections (`Args:`, `Returns:`, `Raises:`), use a 4-space hanging indent; wrap long descriptions consistently.
- **Content over syntax**:
  - Don’t document exceptions raised due to API **misuse** (invalid inputs that violate the contract).
  - Prefer describing **semantics**, constraints, and side effects.
- **Argument names in text**: Do **not** uppercase argument names in running text; use the exact case used in the signature.
- **List arguments**: In `Args:`, **list each argument on its own line**.

### Quick reference examples

```python
# Tuple return:
def qr(a: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Compute a thin QR factorization.

    Returns:
        A tuple `(q, r)` where `q` is orthonormal and `r` is upper-triangular.
    """

# Varargs/kwargs:
def log(msg: str, *args: object, **kwargs: object) -> None:
    """Write a formatted log message.

    Args:
        msg: The format string.
        *args: Positional values interpolated into the format string.
        **kwargs: Keyword values interpolated into the format string.
    """

# Property:
class Session:
    @property
    def token(self) -> str:
        """The current session token."""

# Minimal one-liner:
def ping() -> None:
    """Send a health probe."""
```

## Extra rules

- Identifiers in prose (use backticks)
  - Parameters / variables / attributes: `timeout`, `self.buf`
  - Callables / modules / import paths: `open()`, `package.module.Class`
  - Builtins / exceptions: `list`, `dict`, `len`, `ValueError`, `TypeError`
  - Constants / literals: `None`, `True`, `False`, `0`, `[]`, `{}`
  - CLI flags, env vars, file paths: `--force`, `PATH`, `/var/tmp`
- Third-party names
  - Library/product names as plain words: IPython, NumPy, SciPy, Pandas, PyTorch.
  - API objects as code: `numpy.ndarray`, `pandas.DataFrame`, `torch.no_grad`.
- Literal values & strings
  - Treat exact values as code: `utf-8`, `application/json`, `DEBUG`, `None`, `True`, `False`, `[]`, `{}`.
  - Python string literals include quotes **inside** the backticks: `'utf-8'`, `"warn"`, `r'^\w+$'`.
- Patterns, tokens & paths like regex, glob patterns, environment variables, and file paths: `r'^[A-Z_][A-Z0-9_]*$'`, `*.csv`, `PATH=/usr/local/bin`, `/var/tmp/data`.
- Don’t use bare quotes in prose to mark literals, i.e.,
  - Don’t: “set the mode to 'sync'”
  - Do: “set the mode to `sync`”
- **In `Args:` or `Raises:`**: parameter name is plain text (no backticks).

  ```python
  Args:
      timeout: Seconds to wait before aborting.
  ```

### Math

- Use LaTeX:
  - Inline: `$x^2 + y^2$`
  - Block:

    ```python
    $$
    \operatorname{argmin}_{x \in \mathbb{R}^n} \|Ax-b\|_2^2 + \lambda \|x\|_1
    $$
    ```

- Define symbols at first use (e.g., “where $A \in \mathbb{R}^{m\times n}$”).
