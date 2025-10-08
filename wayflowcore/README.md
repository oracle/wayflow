# wayflowcore

This folder and sub-folders contain the code that constitutes the WayFlow Core library.

## Build (recommended)

Create a Python environment from the root folder.

```bash
$ source ./clean-install-dev.sh
```

This will install wayflowcore in editable mode with the dev dependencies.

## Build (module only)

If you want to install the core module only:

```bash
$ python3 -m venv .venv-wayflowcore
$ source .venv-wayflowcore/bin/activate
$ ./install.sh
```
