# re-renovate
Renovate presets

The renovate app must be enabled for the repository and configured on the default branch using `.github/renovate.json`:
```json
{
    "$schema": "https://docs.renovatebot.com/renovate-schema.json",
    "extends": [
        "github>SonarSource/renovate-config:re-team"
    ]
}
```

## re-team

Updates GitHub Actions and Amazon Machine Images.

### Updating AWS Machine Images in Terraform and Packer projects

Replaces version strings in `*.pkrvars.hcl` and `*.tfvars` files.

#### Syntax
```bash
# renovate: amiFilter=<ami-filter>
# currentImageName=<current-image-name>
<dependency-name> = <image-id>
```

- ami-filter: Use the [DescribeImages filter parameter](https://docs.aws.amazon.com/AWSJavaScriptSDK/v3/latest/client/ec2/command/DescribeImagesCommand/) in minified JSON format.
- current-image-name: The name of the current image. Managed by renovate.
- dependency-name: Use a descriptive variable name for storing the image-id.
- image-id: The ID of the current image. Managed by renovate.

#### Example
```bash
# renovate: amiFilter=[{"Name":"image-type","Values":["machine"]},{"Name":"name","Values":["sonar-image"]},{"Name":"state","Values":["available"]},{"Name":"is-public","Values":["false"]}]
# currentImageName=sonar-image-1.0
sonar_ami_id = "ami-123456789012"
```

### Updating AWS Machine Images in CDK projects

Replaces version strings in `cdk.context.json` files. Works with [LookupMachineImage](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_ec2/LookupMachineImage.html). Only the `name` parameter is used by the manager. Any additional parameters such as `filters` are ignored.

## languages-team

Replaces version strings in `snapshot-generation.sh`.

#### Syntax
```bash
# renovate: datasource=<datasource-name> depName=<repository-name>
export <DEPENDENCY_NAME>_VERSION=<version>
```
- `datasource-name`: The renovate datasource. Use **github-releases**.
- `repository-name`: GitHub owner/repo name to check for new releases.
- `DEPENDENCY_NAME`: Use a descriptive variable name for storing the release version.
- `version`: Version number in the format of `MAJOR.MINOR.PATCH.BUILD`. Managed by renovate.

#### Example
```bash
# renovate: datasource=github-releases depName=SonarSource/sonar-kotlin
export KOTLIN_VERSION=2.15.0.2579
```
