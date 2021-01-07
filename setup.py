import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="empyric-dmerthe",
    version="0.1",
    author="Daniel Merthe",
    author_email="dmerthe@gmail.com",
    description="A python package for building and running experiments",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/pypa/empyric",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)