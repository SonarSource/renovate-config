# @SonarSource/renovate-config

[Shareable config](https://renovatebot.com/docs/config-presets/) for Renovate.

## Presets

### [`default`](default.json)

```json
  "extends": ["github>SonarSource/renovate-config"]
```

Provides authentication credentials to https://repox.jfrog.io. The following package managers were tested for compatibility: `npm`, `maven`, `gradle`, `pipenv`, `poetry`, and `nuget`.

> Note: authentication only works when Renovate is executed using the GitHub app. If you are running locally, see the instructions at [local-testing](#local-testing).

### [`dev-infra-squad`](dev-infra-squad.json)
```json
  "extends": ["github>SonarSource/renovate-config:dev-infra-squad"]
```

Enables the `github-actions` manager and `custom` managers for updating Amazon Machine Images, Cirrus CI modules, and Cirrus CI CLI.

#### AWS Machine Images in Terraform and Packer projects

Replaces version strings in `*.pkrvars.hcl` and `*.tfvars` files.

##### Example

```bash
# amiFilter=[{"Name":"image-type","Values":["machine"]},{"Name":"name","Values":["sonar-image"]},{"Name":"state","Values":["available"]},{"Name":"is-public","Values":["false"]}]
# currentImageName=sonar-image-1.0
sonar_ami_id = "ami-123456789012"

amis = {
  # amiFilter=[{"Name":"image-type","Values":["machine"]},{"Name":"name","Values":["sonar-image"]},{"Name":"state","Values":["available"]},{"Name":"is-public","Values":["false"]}]
  # currentImageName=sonar-image-1.0
  "ubuntu-20.04" = "ami-123456789012"
}
```

- amiFilter: Use
  the [DescribeImages filter parameter](https://docs.aws.amazon.com/AWSJavaScriptSDK/v3/latest/client/ec2/command/DescribeImagesCommand/) in
  minified JSON format.
- currentImageName: The name of the current image. Managed by renovate.
- image_id: The ID of the current image. Managed by renovate.

#### AWS Machine Images in CDK projects

Replaces version strings in `cdk.context.json` files. Works
with [LookupMachineImage](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_ec2/LookupMachineImage.html). Only the `name` parameter
is used by the manager. Any additional parameters such as `filters` are ignored.

#### Cirrus CI modules in the main Starlark files

Replaces Cirrus CI modules version or digest strings in `.cirrus.star` and `lib.star` files.

##### Example

```starlark
# renovate: datasource=github-releases depName=SonarSource/cirrus-modules
load("github.com/SonarSource/cirrus-modules@2.9.0", "load_features")

# renovate: datasource=github-releases depName=SonarSource/cirrus-modules
load("github.com/SonarSource/cirrus-modules@54babd3268dd6daf42ad877100789169a14e5fb3", "load_features")  # 2.9.0
```

#### ghcr.io Docker images in Cirrus CI YAML file

Replaces ghcr.io Docker images version in `.cirrus.yaml`, `.cirrus.yml`.

##### Example

```yaml
  image: ghcr.io/cirruslabs/cirrus-cli:v0.106.0
```
or
```yaml
  image: ghcr.io/cirruslabs/cirrus-cli@sha256:d3fab24e08d1fd7f85826dc1513186bb5423710fdd497e6d9b85debd08d88b42 # v0.106.0
```

#### GitHub Runners ECR Images in YAML files

Replaces Amazon ECR Docker image versions in GitHub runners configuration files located in `infra/applications/github-runners/values/*.yml` and `infra/applications/github-runners/values/*.yaml`.

##### Example

```yaml
RunnerImage: "275878209202.dkr.ecr.eu-central-1.amazonaws.com/base:20241201123456"
```

- `depName`: The ECR repository URL (e.g., `275878209202.dkr.ecr.eu-central-1.amazonaws.com/base`)
- `currentValue`: The current image tag in timestamp format (e.g., `20241201123456`)
- The manager automatically detects and updates the ECR image tags to their latest available versions

### [`languages-team`](languages-team.json)
```json
  "extends": ["github>SonarSource/renovate-config:languates-team"]
```

Enables the `custom` manager for replacing version strings in `snapshot-generation.sh`.

##### Example

```bash
# renovate: datasource=github-releases depName=SonarSource/sonar-kotlin
export KOTLIN_VERSION=2.15.0.2579
```

- `datasource`: The renovate datasource. Should be **github-releases**.
- `depName`: GitHub owner/repo name to check for new releases.
- after the `export` directive use a descriptive variable name for storing the release version. The version number in the format
  of `MAJOR.MINOR.PATCH.BUILD` and is managed by Renovate.

## Development

### Prerequisites

- NodeJS
- [Renovate CLI](https://www.npmjs.com/package/renovate)

### Local Testing

Make changes in your local `.github/renovate.json` file. You might want to reference a shareable config from a branch:

```json
    "extends": ["github>SonarSource/renovate-config:dev-infra-squad#feat/BUILD-1234"]
```


then run Renovate locally:

```bash
GITHUB_COM_TOKEN=$(gh auth token) LOG_LEVEL=debug npx -- renovate --platform=local --secrets '{"REPOX_TOKEN": "${REPOX_TOKEN}"}'
```
