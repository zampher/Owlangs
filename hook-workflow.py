# Custom hook for workflow module
# This hook prevents PyInstaller from looking for a third-party 'workflow' package
# when we actually have a local 'workflow' module in backend/workflow/

# This is a local module, not a package, so we don't need to collect metadata
# Just return empty datas and binaries
datas = []
binaries = []
hiddenimports = []

