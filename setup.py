from setuptools import setup, find_packages
import io
import os

here = os.path.abspath(os.path.dirname(__file__))
readme_path = os.path.join(here, "README.md")
with io.open(readme_path, encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="pipuck-sdk",
    version="0.1.0",
    description="Pi-puck SDK for e-puck2 and peripherals",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Omri",
    url="https://github.com/OmriPer/pipuck-sdk",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: POSIX :: Linux",
    ],
    python_requires=">=3.5",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "smbus2>=0.4.2",
    ],
    entry_points={
        "console_scripts": [
            "pipuck-swarm=pipuck.swarm_cli:main",
        ],
    },
    include_package_data=True,
)
