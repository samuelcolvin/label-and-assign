#!/usr/bin/env python3
import logging
import sys
from typing import Optional, Tuple

from github import Github
from pydantic import BaseModel, BaseSettings, FilePath, SecretStr, ValidationError, validator


class Settings(BaseSettings):
    github_repository: str
    github_event_path: FilePath
    token: SecretStr
    reviewers: Tuple[str, ...]
    request_update_trigger: str
    request_review_trigger: str
    awaiting_update_label: str
    awaiting_review_label: str

    @validator('reviewers', pre=True)
    def parse_reviewers(cls, rs: str) -> Tuple[str, ...]:
        reviewers = [r.strip(' ') for r in rs.split(',')]
        return tuple(filter(None, reviewers))

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


class PullRequest(BaseModel):
    url: str


class Issue(BaseModel):
    pull_request: Optional[PullRequest] = None
    user: User
    number: int


class GitHubEvent(BaseModel):
    comment: Comment
    issue: Issue


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
            self.event = GitHubEvent.parse_raw(contents)

            if self.event.issue.pull_request is None:
                logging.info('action only applies to pull requests, not issues')
                sys.exit(0)

            g = Github(self.settings.token.get_secret_value())
            repo = g.get_repo(self.settings.github_repository)
            self.pr = repo.get_pull(self.event.issue.number)
            self.commenter_is_reviewer = self.event.comment.user.login in self.settings.reviewers
            self.commenter_is_author = self.event.issue.user.login == self.event.comment.user.login
            self.show_reviewers = ', '.join(f'"{r}"' for r in self.settings.reviewers)

    def run(self):
        body = self.event.comment.body.lower()
        if self.settings.request_update_trigger in body:
            success, msg = self.assigned_author()
        elif self.settings.request_review_trigger in body:
            success, msg = self.request_review()
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

    def assigned_author(self) -> Tuple[bool, str]:
        if not self.commenter_is_reviewer:
            return (
                False,
                f'Only reviewers {self.show_reviewers} can assign the author, not {self.event.comment.user.login}',
            )
        self.pr.add_to_labels(self.settings.awaiting_update_label)
        self.remove_label(self.settings.awaiting_review_label)
        self.pr.add_to_assignees(self.event.issue.user.login)
        to_remove = [r for r in self.settings.reviewers if r != self.event.issue.user.login]
        if to_remove:
            self.pr.remove_from_assignees(*to_remove)
        return (
            True,
            f'Author {self.event.issue.user.login} successfully assigned to PR, '
            f'"{self.settings.awaiting_update_label}" label added',
        )

    def request_review(self) -> Tuple[bool, str]:
        if not (self.commenter_is_reviewer or self.commenter_is_author):
            return False, (
                f'Only the PR author {self.event.issue.user.login} or reviewers can request a review, '
                f'not {self.event.comment.user.login}'
            )
        self.pr.add_to_labels(self.settings.awaiting_review_label)
        self.remove_label(self.settings.awaiting_update_label)
        self.pr.add_to_assignees(*self.settings.reviewers)
        if self.event.issue.user.login not in self.settings.reviewers:
            self.pr.remove_from_assignees(self.event.issue.user.login)
        return (
            True,
            f'Reviewers {self.show_reviewers} successfully assigned to PR, '
            f'"{self.settings.awaiting_review_label}" label added',
        )

    def remove_label(self, label: str):
        labels = self.pr.get_labels()
        if any(lb.name == label for lb in labels):
            self.pr.remove_from_labels(label)


if __name__ == '__main__':
    r = Run()
    if r.settings is None:
        sys.exit(1)
    else:
        r.run()
