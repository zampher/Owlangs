# Runtime hook to register utils alias for backend.utils
# This runs very early in the PyInstaller frozen application
import sys

# Register utils -> backend.utils alias early
if 'backend.utils' in sys.modules:
    sys.modules['utils'] = sys.modules['backend.utils']
    # Also register submodules
    for name, module in list(sys.modules.items()):
        if name.startswith('backend.utils.'):
            subname = name.replace('backend.utils.', 'utils.')
            sys.modules[subname] = module
