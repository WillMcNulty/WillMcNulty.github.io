import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import updates  # noqa: E402


class SanitizeTests(unittest.TestCase):
    def test_summary_never_contains_commit_text(self):
        messages = ["Add Initech Analyst Intern to the tracker", "Fix Globex Corp follow-up date"]
        summary = updates.summarize(messages)
        for secret in ("Initech", "Globex", "Intern", "follow-up"):
            self.assertNotIn(secret, summary)
        self.assertEqual(summary, "Work on new features and bug fixes.")

    def test_unrecognized_message_falls_back_to_generic_wording(self):
        self.assertEqual(updates.summarize(["Jane Doe transcript 3.6 GPA"]), "Work on general improvements.")

    def test_no_commits_gives_no_summary(self):
        self.assertEqual(updates.summarize([]), "")

    def test_only_listed_repos_are_read(self):
        asked = []

        def fake(repo, since):
            asked.append(repo)
            return [("2026-09-21T10:00:00Z", "Add thing")]

        config = {"projects": [{"repo": "me/listed", "title": "Public Title"}]}
        projects = updates.build_projects(config, datetime(2026, 9, 1, tzinfo=timezone.utc), fetch=fake)
        self.assertEqual(asked, ["me/listed"])
        self.assertEqual(projects[0]["title"], "Public Title")
        self.assertNotIn("listed", str(projects))

    def test_projects_without_activity_are_left_out(self):
        projects = updates.build_projects(
            {"projects": [{"repo": "me/quiet", "title": "Quiet"}]},
            datetime(2026, 9, 1, tzinfo=timezone.utc),
            fetch=lambda repo, since: [],
        )
        self.assertEqual(projects, [])


class WindowTests(unittest.TestCase):
    config = {"start": "2026-09-01"}

    def test_starts_at_config_date_when_nothing_else_exists(self):
        start = updates.window_start(self.config, [], {"periods": []})
        self.assertEqual(updates.stamp(start), "2026-09-01T00:00:00Z")

    def test_newest_of_post_and_last_report_wins(self):
        data = {"periods": [{"end": "2026-09-10T12:00:00Z"}]}
        posts = [{"date": "2026-09-05"}, {"date": "2026-09-12"}]
        self.assertEqual(updates.stamp(updates.window_start(self.config, posts, data)), "2026-09-12T00:00:00Z")
        posts = [{"date": "2026-09-05"}]
        self.assertEqual(updates.stamp(updates.window_start(self.config, posts, data)), "2026-09-10T12:00:00Z")


if __name__ == "__main__":
    unittest.main()
