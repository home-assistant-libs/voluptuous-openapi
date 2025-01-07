from setuptools import setup

setup(
    name="voluptuous-openapi",
    version="0.0.6",
    description="Convert voluptuous schemas to OpenAPI Schema object",
    url="https://github.com/home-assistant-libs/voluptuous-openapi",
    author="Denis Shulyaka",
    author_email="Shulyaka@gmail.com",
    license="Apache License 2.0",
    install_requires=["voluptuous"],
    packages=["voluptuous_openapi"],
    zip_safe=True,
)
