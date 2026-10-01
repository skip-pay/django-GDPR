import os

from gdpr.version import get_version
from setuptools import find_packages, setup


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name='skip-django-GDPR',
    long_description=read('README.md'),
    long_description_content_type='text/markdown',
    version=get_version(),
    description='Library for GDPR implementation',
    author='Druids',
    author_email='matllubos@gmail.com',
    url='https://github.com/skip-pay/django-GDPR',
    license='MIT',
    package_dir={'gdpr': 'gdpr'},
    include_package_data=True,
    packages=find_packages(),
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Framework :: Django',
        'Framework :: Django :: 5.2',
        'Framework :: Django :: 6.0',
        'Framework :: Django :: 6.1',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.14',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
    python_requires='>=3.14',
    install_requires=[
        'django>=5.2,<6.2',
        'skip-django-chamber>=0.7.2',
        'tqdm>=4.28.1',
        'pyaes>=1.6.1',
        'unidecode',
        'skip-django-choice-enumfields>=1.1.3.2',
    ],
    zip_safe=False,
)
