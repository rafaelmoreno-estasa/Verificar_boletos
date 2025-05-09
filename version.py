# https://stackoverflow.com/questions/458550/standard-way-to-embed-version-into-python-package

# Store the version here so:
# 1) we don't load dependencies by storing it in __init__.py
# 2) we can import it in setup.py for the same reason
# 3) we can import it into your module module
__version_info__ = ('2025', '4', '2')
__version__ = '.'.join(__version_info__)
