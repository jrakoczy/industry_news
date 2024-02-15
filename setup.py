from setuptools import setup, find_packages

setup(
    name="industry_news",
    version="0.1",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    package_data={"industry_news": ["py.typed"]},
)