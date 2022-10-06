import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="empyric-dmerthe",
    version="0.1",
    author="Daniel Merthe",
    author_email="dmerthe@gmail.com",
    description="A package for experiment automation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/dmerthe/empyric",
    packages=setuptools.find_packages(),
    package_data={'': ['*.yaml']},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=[
        'numpy',
        'scipy',
        'matplotlib',
        'pandas',
        'pykwalify',
        'ruamel.yaml'
    ],
    entry_points={'console_scripts': ['empyric = empyric:execute', ]}
)
