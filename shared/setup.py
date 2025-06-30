from setuptools import setup, find_packages

setup(
    name="shared",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "pydantic>=2.0",
        "motor>=3.0",
        "python-dotenv>=1.0",
    ],
    python_requires=">=3.10",
)