import yaml

requirements_directory = "requirements"

ignores = [
    "mypy",
    "psycopg2",
]

extras = [
    "psycopg2-binary",
]

def clean_line(line: str):
    """
    Clean the line
    """
    if any(ignore in line for ignore in ignores):
        return None

    output = ""
    for char in line:
        if char == '#':
            break
        if char:
            output += char
    return output.strip()

def get_requirements_from_requirements_file(requirements_file: str):
    """
    Get the requirements from the requirements file
    """
    requirements = []
    with open(f"{requirements_directory}/{requirements_file}") as f:
        for line in f.readlines():
            line = line.strip()
            if line.startswith('-r'):
                requirements.extend(get_requirements_from_requirements_file(line[3:]))
            else:
                line = clean_line(line)
                if line:
                    requirements.append(line)

    return requirements

def write_requirements_to_precommit_config(requirements: list, precommit_config_file: str):
    """
    Write the requirements to the precommit config file
    """
    print(requirements)
    with open(precommit_config_file, 'r') as f:
        config = yaml.safe_load(f)

    repos = config['repos']
    mypy_repo = next(repo for repo in repos if repo['repo'] == 'https://github.com/pre-commit/mirrors-mypy')

    mypy_repo['hooks'][0]['additional_dependencies'] = requirements

    with open(precommit_config_file, 'w') as f:
        yaml.dump(config, f)

requirements = get_requirements_from_requirements_file('local.txt') + extras
write_requirements_to_precommit_config(requirements, '.pre-commit-config.yaml')
