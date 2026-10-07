import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from lxml import etree

import today


ROOT = Path(__file__).resolve().parents[1]


class ProfileUpdateTests(unittest.TestCase):
    def test_both_themes_update_data_without_changing_art_or_static_profile(self):
        for theme in ('dark_mode.svg', 'light_mode.svg'):
            with self.subTest(theme=theme), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / theme
                path.write_bytes((ROOT / theme).read_bytes())
                before = etree.parse(str(path))
                art = before.xpath('//*[local-name()="text" and @class="ascii"]')[0]
                original_art = etree.tostring(art)
                original_static = [element.text for element in before.xpath(
                    '//*[local-name()="tspan" and not(@id)]')]

                today.svg_overwrite(str(path), '24 years, 3 months, 2 days',
                                    2345, 456, 123, 150, 250,
                                    [600000, 100000, 500000],
                                    today.profile_values({'login': 'hemanshulabs',
                                        'websiteUrl': 'https://hemanshu-portfolio.vercel.app'}))

                after = etree.parse(str(path))
                for element_id, value in {
                    'age_data': '24 years, 3 months, 2 days',
                    'commit_data': '2,345', 'star_data': '456',
                    'repo_data': '123', 'contrib_data': '150',
                    'follower_data': '250', 'loc_data': '500,000',
                    'loc_add': '600,000', 'loc_del': '100,000',
                }.items():
                    self.assertEqual(after.xpath(f'//*[@id="{element_id}"]')[0].text, value)
                self.assertEqual(etree.tostring(after.xpath(
                    '//*[local-name()="text" and @class="ascii"]')[0]), original_art)
                self.assertEqual([element.text for element in after.xpath(
                    '//*[local-name()="tspan" and not(@id)]')], original_static)
                self.assertEqual(after.xpath('//*[@id="profile_data"]')[0].text,
                                 'hemanshulabs@github')
                self.assertEqual(after.xpath('//*[@id="kernel_data"]')[0].text,
                                 today.profile_values({'login': 'hemanshulabs'})['kernel_data'])
                for field in ('programming', 'computer', 'infrastructure', 'concepts', 'ai'):
                    expected = today.profile_values({'login': 'hemanshulabs'})[field + '_data']
                    self.assertEqual(after.xpath(f'//*[@id="{field}_data"]')[0].text, expected)
                website = after.xpath('//*[@id="website_data"]')[0]
                self.assertEqual(website.text, today.profile_values({'login': 'hemanshulabs'})['website_data'])
                self.assertLessEqual(len(website.text) + len(website.getprevious().text) +
                                     len('. Website.Personal:'), 60)

    def test_stars_include_every_repository_page(self):
        def page(stars, cursor, has_next):
            return Mock(json=lambda: {'data': {'user': {'repositories': {
                'totalCount': 101,
                'edges': [{'node': {'stargazers': {'totalCount': stars}}}],
                'pageInfo': {'endCursor': cursor, 'hasNextPage': has_next},
            }}}})

        with patch.object(today, 'simple_request', side_effect=[
            page(400, 'next-page', True), page(56, 'last-page', False)
        ]) as request:
            self.assertEqual(today.graph_repos_stars('stars', ['OWNER']), 456)
            self.assertEqual(request.call_args_list[1].args[2]['cursor'], 'next-page')

    def test_graphql_errors_stop_updates_even_with_http_200(self):
        response = Mock(status_code=200)
        response.json.return_value = {'errors': [{'message': 'Permission denied'}]}
        with patch.object(today.requests, 'post', return_value=response):
            with self.assertRaisesRegex(RuntimeError, 'Permission denied'):
                today.simple_request('test', 'query {}', {})

    def test_profile_uses_github_identity_and_does_not_invent_contacts(self):
        values = today.profile_values({
            'login': 'hemanshulabs', 'company': None, 'email': None,
            'websiteUrl': 'https://hemanshu-portfolio.vercel.app',
        })
        self.assertEqual(values['profile_data'], 'hemanshulabs@github')
        self.assertEqual(values['email_data'], 'hemanshuypatil@gmail.com')
        self.assertEqual(values['website_data'], 'hemanshulabs.vercel.app')

    def test_history_queries_only_the_profile_accounts_commits(self):
        response = Mock(status_code=200)
        response.json.return_value = {'data': {'repository': {'defaultBranchRef': {
            'target': {'history': {'edges': [], 'pageInfo': {'hasNextPage': False}}}
        }}}}
        with patch.object(today, 'OWNER_ID', {'id': 'account-id'}, create=True), \
                patch.object(today, 'simple_request', return_value=response) as request:
            self.assertEqual(today.recursive_loc('owner', 'repo', [], []), (0, 0, 0))
            self.assertEqual(request.call_args.args[2]['author_id'], 'account-id')
            self.assertIn('author: {id: $author_id}', request.call_args.args[1])


if __name__ == '__main__':
    unittest.main()
