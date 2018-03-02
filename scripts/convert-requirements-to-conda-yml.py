# encoding=UTF-8
"""convert-requirements-to-conda-yml.py"""

import sys
import requests
import pkg_resources

FEEDSTOCK_URL = 'https://github.com/conda-forge/{package}-feedstock'
YML_TEMPLATE = """name: invest-env
channels:
- conda-forge
- default
dependencies:
{conda_dependencies}
{pip_dependencies}
"""


def main():
    pip_requirements = set([])
    conda_requirements = set([])
    for line in open('requirements.txt'):
        line = line.strip()
        if len(line) == 0 or line.startswith('#'):
            continue

        if line.startswith(('hg', 'git', 'svn', 'bzr')):
            pip_requirements.add(line)
            continue

        requirement = pkg_resources.Requirement.parse(line)
        conda_forge_url = FEEDSTOCK_URL.format(
            package=requirement.project_name.lower())
        if requests.get(conda_forge_url).status_code == 200:
            conda_requirements.add(line)
        else:
            pip_requirements.add(line)

    conda_deps_string = '\n'.join(['- %s' % dep for dep in conda_requirements])
    pip_deps_string = '- pip:\n' + '\n'.join(['  - %s' % dep for dep in pip_requirements])
    print YML_TEMPLATE.format(
        conda_dependencies=conda_deps_string,
        pip_dependencies=pip_deps_string)


if __name__ == '__main__':
    main()
