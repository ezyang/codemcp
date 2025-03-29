## python

Reasoning behind decisions:

- Adopt as many `uv init` defaults as possible, e.g., py.typed by default.

- `_internal` directory to encourage no public API by default.  Hopefully
  induce LLM to be willing to do refactors without leaving BC shims lying
  around.

- Build system: hatchling.  uv default.  We do want a build backend so that
  CLI tool invocation works.

- Python version: the latest.  If uv is managing your Python install for a CLI
  there's no reason not to use the latest Python, UNLESS you have a dependency
  that specifically needs something earlier.  (Library would make different
  decision here.)

- Version bounds on built-in dependencies: latest possible, because that is
  the 'uv add' default.  We will need to occasionally rev these though.
