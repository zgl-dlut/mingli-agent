from setuptools import setup, find_packages

setup(
    name="sxwnl",
    version="1.0.0",
    packages=find_packages(),
    include_package_data=True,
    package_data={"sxwnl": ["*.pkl", "*.json"]},
)
