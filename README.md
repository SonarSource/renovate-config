# @SonarSource/renovate-config

[Shareable config](https://renovatebot.com/docs/config-presets/) for Renovate.

## Setup

1. The [Renovate app](https://developer.mend.io/) must be enabled for the repository. Reach out to the [DevInfra Squad](https://sonarsource.enterprise.slack.com/archives/C04CVEU7734) if that is not the case.
2. Add `.github/renovate.json` to the repository 
```json title="index.json"
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": [
    "github>SonarSource/renovate-config:slim"
  ]
}
```

## Presets
### [`slim`](slim.json)

Enables the `github-actions` manager.

### [`re-team`](re-team.json)

Enables the `github-actions` manager and the `custom` manager for updating Amazon Machine Images and CirrusCI modules.

#### Updating AWS Machine Images in Terraform and Packer projects

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

#### Updating AWS Machine Images in CDK projects

Replaces version strings in `cdk.context.json` files. Works
with [LookupMachineImage](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_ec2/LookupMachineImage.html). Only the `name` parameter
is used by the manager. Any additional parameters such as `filters` are ignored.

#### Updating CirrusCI modules in main Starlark file

Replaces CirrusCI modules version or digest strings in `.cirrus.star` file.

##### Example

```starlark
# renovate: datasource=github-releases depName=SonarSource/cirrus-modules
load("github.com/SonarSource/cirrus-modules@2.9.0", "load_features")

# renovate: datasource=github-releases depName=SonarSource/cirrus-modules
load("github.com/SonarSource/cirrus-modules@54babd3268dd6daf42ad877100789169a14e5fb3", "load_features")  # 2.9.0
```

### [`languages-team`](languages-team.json)

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

Copy the configuration to test to the target repository in `.github/renovate.json`.

Remove the `extends` key and eventually replace it with the content of the preset files.

Run Renovate locally:

```bash
GITHUB_COM_TOKEN=$(gh auth token) LOG_LEVEL=debug npx -- renovate --platform=local
```
