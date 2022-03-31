#!/usr/bin/env python3

from setuptools import setup, find_packages


with open('README.md', 'rt') as f:
    long_description = f.read()

with open('snarled/VERSION.py', 'rt') as f:
    version = f.readlines()[2].strip()

setup(name='snarled',
      version=version,
      description='CAD layout electrical connectivity checker',
      long_description=long_description,
      long_description_content_type='text/markdown',
      author='Jan Petykiewicz',
      author_email='jan@mpxd.net',
      url='https://mpxd.net/code/jan/snarled',
      packages=find_packages(),
      package_data={
          'snarled': ['py.typed',
                    ]
      },
      install_requires=[
          'numpy',
          'pyclipper',
      ],
      extras_require={
          'masque': ['masque'],
          'oasis': ['fatamorgana>=0.7'],
          'gdsii': ['klamath>=1.0'],
      },
      classifiers=[
            'Programming Language :: Python :: 3',
            'Development Status :: 4 - Beta',
            'Intended Audience :: Developers',
            'Intended Audience :: Information Technology',
            'Intended Audience :: Manufacturing',
            'Intended Audience :: Science/Research',
            'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
            'Topic :: Scientific/Engineering :: Electronic Design Automation (EDA)',
      ],
      keywords=[
          'layout',
          'design',
          'CAD',
          'EDA',
          'electronics',
          'photonics',
          'IC',
          'mask',
          'pattern',
          'drawing',
          'lvs',
          'connectivity',
          'short',
          'unintentional',
          'label',
          'schematic',
      ],
      )

