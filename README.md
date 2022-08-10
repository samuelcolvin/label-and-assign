# Label & Assign

Switch labels and assignees on pull requests using comments.

This is useful to manage the review process when pull request authors are not approved contributors.

## Usage

Install this GitHub action by creating a file in your repo at `.github/workflows/label-assign.yml`.

A minimal example:

```yaml
name: Label & Assign

on:
  issue_comment:
    types: [created, edited]

permissions:
  pull-requests: write

jobs:
  label-and-assign:
    runs-on: ubuntu-latest
    steps:
      - uses: docker://samuelcolvin/label-and-assign:latest
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          reviewers: first_reviewer, second_reviewer
```

### Performance

This action is available from the GitHub actions marketplace under the name 
[`samuelcolvin/label-and-assign`](https://github.com/marketplace/actions/label-assign) however because its container 
based and GitHub actions can't cache container builds of actions, it's much faster to use via a pre-built image
from Docker Hub [`samuelcolvin/label-and-assign`](https://hub.docker.com/r/samuelcolvin/label-and-assign).

Use of the pre-built image is shown in the image above.

### Inputs

* **`token`**: Github token for the repo, use `{{ secrets.GITHUB_TOKEN }}` (**required**)
* **`reviewers`**: Comma separated list of Github usernames for pull request reviewers (**required**)
* **`request_update_trigger`**: Text to search for in comments by reviewers to trigger a request for
  changes from the PR author, case-insensitive (default: `please update`)
* **`request_review_trigger`**: Text to search for in comments by the PR author to trigger a request for reviews from
  the Reviewers, case-insensitive (default: `please review`)
* **`awaiting_update_label`**: Label to apply when an update is requested, 
  this label needs to exist of the action will fail (default: `awaiting author updates`)
* **`awaiting_review_label`**: Label to apply when a review is requested, 
  this label needs to exist of the action will fail required: false (default: `awaiting review`)

xxx
