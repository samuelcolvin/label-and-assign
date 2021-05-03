#!/usr/bin/env python3
import logging
import sys
from typing import Optional, Tuple, Union, cast

from github import Github
from pydantic import BaseModel, BaseSettings, FilePath, SecretStr, ValidationError, parse_raw_as


class Settings(BaseSettings):
    github_repository: str
    github_event_path: FilePath
    token: SecretStr
    reviewers: str
    request_update_trigger: str
    request_review_trigger: str
    awaiting_update_label: str
    awaiting_review_label: str

    class Config:
        fields = {
            'token': {'env': 'input_token'},
            'reviewers': {'env': ['input_reviewers']},
            'request_update_trigger': {'env': ['input_request_update_trigger']},
            'request_review_trigger': {'env': ['input_request_review_trigger']},
            'awaiting_update_label': {'env': ['input_awaiting_update_label']},
            'awaiting_review_label': {'env': ['input_awaiting_review_label']},
        }


class User(BaseModel):
    login: str


class Comment(BaseModel):
    body: str
    user: User


class IssuePullRequest(BaseModel):
    url: str


class Issue(BaseModel):
    pull_request: Optional[IssuePullRequest] = None
    user: User
    number: int


class IssueEvent(BaseModel):
    comment: Comment
    issue: Issue


class Review(BaseModel):
    body: str
    user: User
    state: str


class PullRequest(BaseModel):
    number: int
    user: User


class PullRequestEvent(BaseModel):
    review: Review
    pull_request: PullRequest


logging.basicConfig(level=logging.INFO)


class Run:
    def __init__(self):
        try:
            self.settings = Settings()
        except ValidationError as e:
            logging.error('error loading Settings\n:%s', e)
            self.settings = None
        else:
            contents = self.settings.github_event_path.read_text()
            event = parse_raw_as(Union[IssueEvent, PullRequestEvent], contents)
            self.force_assign_author = False

            if issue := getattr(event, 'issue', None):
                event = cast(IssueEvent, event)
                if issue.pull_request is None:
                    logging.info('action only applies to pull requests, not issues')
                    self.settings = None
                    return

                self.commenter = event.comment.user.login
                number = event.issue.number
                self.author = event.issue.user.login
                self.body = event.comment.body.lower()
                self.type = 'comment'
            else:
                event = cast(PullRequestEvent, event)
                self.commenter = event.review.user.login
                number = event.pull_request.number
                self.author = event.pull_request.user.login
                self.body = event.review.body.lower()
                self.force_assign_author = event.review.state == 'changes_requested'
                self.type = 'review'

            # hack until https://github.com/samuelcolvin/pydantic/issues/1458 gets fixed
            self.reviewers = [r.strip(' ') for r in self.settings.reviewers.split(',') if r.strip(' ')]

            g = Github(self.settings.token.get_secret_value())
            repo = g.get_repo(self.settings.github_repository)
            self.pr = repo.get_pull(number)
            self.commenter_is_reviewer = self.commenter in self.reviewers
            self.commenter_is_author = self.author == self.commenter

    def run(self):
        logging.info('%s (%s): %r', self.commenter, self.type, self.body)
        if self.settings.request_review_trigger in self.body:
            success, msg = self.request_review()
        elif self.settings.request_update_trigger in self.body or self.force_assign_author:
            success, msg = self.assign_author()
        else:
            success = True
            msg = (
                f'neither {self.settings.request_update_trigger!r} nor {self.settings.request_review_trigger!r} '
                f'found in comment body, not proceeding'
            )

        if success:
            logging.info('success: %s', msg)
        else:
            logging.warning('warning: %s', msg)

    def assign_author(self) -> Tuple[bool, str]:
        if not self.commenter_is_reviewer:
            return (
                False,
                f'Only reviewers {self.show_reviewers()} can assign the author, not {self.commenter}',
            )
        self.pr.add_to_labels(self.settings.awaiting_update_label)
        self.remove_label(self.settings.awaiting_review_label)
        self.pr.add_to_assignees(self.author)
        to_remove = [r for r in self.reviewers if r != self.author]
        if to_remove:
            self.pr.remove_from_assignees(*to_remove)
        return (
            True,
            f'Author {self.author} successfully assigned to PR, '
            f'"{self.settings.awaiting_update_label}" label added',
        )

    def request_review(self) -> Tuple[bool, str]:
        if not (self.commenter_is_reviewer or self.commenter_is_author):
            return False, (
                f'Only the PR author {self.author} or reviewers can request a review, not {self.commenter}'
            )
        self.pr.add_to_labels(self.settings.awaiting_review_label)
        self.remove_label(self.settings.awaiting_update_label)
        self.pr.add_to_assignees(*self.reviewers)
        if self.author not in self.reviewers:
            self.pr.remove_from_assignees(self.author)
        return (
            True,
            f'Reviewers {self.show_reviewers()} successfully assigned to PR, '
            f'"{self.settings.awaiting_review_label}" label added',
        )

    def remove_label(self, label: str):
        labels = self.pr.get_labels()
        if any(lb.name == label for lb in labels):
            self.pr.remove_from_labels(label)

    def show_reviewers(self):
        return ', '.join(f'"{r}"' for r in self.reviewers)


if __name__ == '__main__':
    run = Run()
    if run.settings is None:
        sys.exit(1)
    else:
        run.run()
