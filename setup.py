from setuptools import setup

version = open('VERSION').read()
setup(
    name='redis_opentracing',
    version=version,
    url='https://github.com/opentracing-contrib/python-redis/',
    download_url='https://github.com/opentracing-contrib/python-redis/tarball/'+version,
    license='BSD',
    author='Carlos Alberto Cortez',
    author_email='calberto.cortez@gmail.com',
    description='OpenTracing support for Elasticsearch',
    long_description=open('README.rst').read(),
    packages=['redis_opentracing'],
    platforms='any',
    install_requires=[
        'redis',
        'opentracing>=1.1,<1.2'
    ],
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
