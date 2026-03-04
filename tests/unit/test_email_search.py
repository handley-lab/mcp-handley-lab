"""Tests for email search auto-relaxation, folder families, and query parsing."""

from unittest.mock import MagicMock, patch

from mcp_handley_lab.email.notmuch.shared import (
    _auto_relax,
    _build_folder_families,
    _expand_folder_families,
    _extract_query_clauses,
    _normalize_folder_query,
    _notmuch_count,
    _parse_query_tokens,
    _relax_query,
)

# ============================================================================
# TestNotmuchCount
# ============================================================================


class TestNotmuchCount:
    @patch("mcp_handley_lab.email.notmuch.shared.subprocess.run")
    def test_basic_count(self, mock_run):
        mock_run.return_value = MagicMock(stdout="42\n")
        assert _notmuch_count("tag:inbox") == 42
        mock_run.assert_called_once_with(
            ["notmuch", "count", "tag:inbox"],
            check=True,
            text=True,
            capture_output=True,
        )

    @patch("mcp_handley_lab.email.notmuch.shared.subprocess.run")
    def test_include_excluded(self, mock_run):
        mock_run.return_value = MagicMock(stdout="5\n")
        _notmuch_count("tag:spam", include_excluded=True)
        mock_run.assert_called_once_with(
            ["notmuch", "count", "--exclude=false", "tag:spam"],
            check=True,
            text=True,
            capture_output=True,
        )

    @patch("mcp_handley_lab.email.notmuch.shared.subprocess.run")
    def test_error_returns_negative(self, mock_run):
        from subprocess import CalledProcessError

        mock_run.side_effect = CalledProcessError(1, "notmuch")
        assert _notmuch_count("invalid:query") == -1


# ============================================================================
# TestFolderFamilies
# ============================================================================


class TestFolderFamilies:
    def test_year_suffix_family(self):
        folders = [
            "Acct/Sent Items",
            "Acct/Sent Items.2024",
            "Acct/Sent Items.2023",
        ]
        families = _build_folder_families(folders)
        assert "Acct/Sent Items" in families
        # Base first, then years ascending
        assert families["Acct/Sent Items"] == [
            "Acct/Sent Items",
            "Acct/Sent Items.2023",
            "Acct/Sent Items.2024",
        ]

    def test_topic_suffix_excluded(self):
        folders = [
            "Acct/Archive",
            "Acct/Archive.PhD",
            "Acct/Archive.CATAM",
        ]
        families = _build_folder_families(folders)
        assert "Acct/Archive" not in families

    def test_inbox_subfolders_excluded(self):
        folders = ["Acct/INBOX", "Acct/INBOX.PhD", "Acct/INBOX.GitHub"]
        families = _build_folder_families(folders)
        assert "Acct/INBOX" not in families

    def test_base_absent(self):
        folders = ["Acct/Sent.2024", "Acct/Sent.2023"]
        families = _build_folder_families(folders)
        assert "Acct/Sent" in families
        # Base not in folders, so not included
        assert families["Acct/Sent"] == ["Acct/Sent.2023", "Acct/Sent.2024"]

    def test_singleton_excluded(self):
        folders = ["Acct/Sent.2024"]
        families = _build_folder_families(folders)
        assert families == {}

    def test_empty_input(self):
        assert _build_folder_families([]) == {}

    def test_mixed_folders(self):
        folders = [
            "Acct/Sent Items",
            "Acct/Sent Items.2024",
            "Acct/Sent Items.2023",
            "Acct/Archive",
            "Acct/Archive.PhD",
            "Acct/INBOX",
            "Acct/INBOX.PhD",
        ]
        families = _build_folder_families(folders)
        assert set(families.keys()) == {"Acct/Sent Items"}


# ============================================================================
# TestExpandFolderFamilies
# ============================================================================


class TestExpandFolderFamilies:
    FAMILIES = {
        "Acct/Sent Items": [
            "Acct/Sent Items",
            "Acct/Sent Items.2023",
            "Acct/Sent Items.2024",
        ],
    }

    def test_expand_base(self):
        result = _expand_folder_families('folder:"Acct/Sent Items"', self.FAMILIES)
        assert result == (
            '(folder:"Acct/Sent Items" OR '
            'folder:"Acct/Sent Items.2023" OR '
            'folder:"Acct/Sent Items.2024")'
        )

    def test_no_family_unchanged(self):
        query = 'folder:"Acct/INBOX"'
        assert _expand_folder_families(query, self.FAMILIES) == query

    def test_no_folder_unchanged(self):
        query = "from:boss subject:hello"
        assert _expand_folder_families(query, self.FAMILIES) == query

    def test_empty_families_unchanged(self):
        query = 'folder:"Acct/Sent Items"'
        assert _expand_folder_families(query, {}) == query

    def test_negated_dash_not_expanded(self):
        query = '-folder:"Acct/Sent Items"'
        assert _expand_folder_families(query, self.FAMILIES) == query

    def test_negated_not_keyword_not_expanded(self):
        query = 'NOT folder:"Acct/Sent Items"'
        assert _expand_folder_families(query, self.FAMILIES) == query

    def test_negated_lowercase_not_expanded(self):
        query = 'not folder:"Acct/Sent Items"'
        assert _expand_folder_families(query, self.FAMILIES) == query

    def test_negated_multiple_spaces_not_expanded(self):
        query = 'NOT  folder:"Acct/Sent Items"'
        assert _expand_folder_families(query, self.FAMILIES) == query

    def test_not_inside_quotes_does_expand(self):
        query = 'subject:"NOT folder:Sent" folder:"Acct/Sent Items"'
        result = _expand_folder_families(query, self.FAMILIES)
        # subject value is skipped, folder: is expanded
        assert 'folder:"Acct/Sent Items.2023"' in result
        assert 'folder:"Acct/Sent Items.2024"' in result

    def test_year_specific_not_expanded(self):
        query = 'folder:"Acct/Sent Items.2024"'
        assert _expand_folder_families(query, self.FAMILIES) == query

    def test_base_absent_expansion(self):
        families = {
            "Acct/Sent": ["Acct/Sent.2023", "Acct/Sent.2024"],
        }
        result = _expand_folder_families('folder:"Acct/Sent"', families)
        assert result == '(folder:"Acct/Sent.2023" OR folder:"Acct/Sent.2024")'

    def test_inside_parens_not_expanded(self):
        query = '(folder:"Acct/Sent Items" OR tag:inbox)'
        assert _expand_folder_families(query, self.FAMILIES) == query

    def test_bare_folder_expanded(self):
        families = {"INBOX": ["INBOX", "INBOX.2023", "INBOX.2024"]}
        result = _expand_folder_families("folder:INBOX", families)
        assert (
            result == '(folder:"INBOX" OR folder:"INBOX.2023" OR folder:"INBOX.2024")'
        )


# ============================================================================
# TestExtractQueryClauses
# ============================================================================


class TestExtractQueryClauses:
    def test_basic_extraction(self):
        query = 'folder:"Acct/INBOX" from:boss@co.uk date:2024-01-01.. free text'
        clauses = _extract_query_clauses(query)
        assert clauses["folder"] == ['"Acct/INBOX"']
        assert clauses["from"] == ["boss@co.uk"]
        assert clauses["date"] == ["2024-01-01.."]
        assert "free text" in clauses["remainder"]

    def test_quoted_from(self):
        query = 'from:"Name <x@y>"'
        clauses = _extract_query_clauses(query)
        assert clauses["from"] == ['"Name <x@y>"']

    def test_bare_from(self):
        clauses = _extract_query_clauses("from:boss")
        assert clauses["from"] == ["boss"]

    def test_inside_parens_goes_to_remainder(self):
        query = "(from:a OR from:b) AND subject:X"
        clauses = _extract_query_clauses(query)
        # from: inside parens not extracted
        assert clauses["from"] == []
        assert "from:a" in clauses["remainder"] or "(from:a" in clauses["remainder"]

    def test_parens_in_quotes_dont_affect_depth(self):
        query = 'subject:"status (draft)" folder:Sent'
        clauses = _extract_query_clauses(query)
        assert clauses["folder"] == ["Sent"]

    def test_date_range(self):
        query = "date:2024-01-01..2024-06-01 from:alice"
        clauses = _extract_query_clauses(query)
        assert clauses["date"] == ["2024-01-01..2024-06-01"]
        assert clauses["from"] == ["alice"]

    def test_negated_not_extracted(self):
        query = "-folder:Spam from:alice"
        clauses = _extract_query_clauses(query)
        assert clauses["folder"] == []  # negated, not extracted
        assert clauses["from"] == ["alice"]

    def test_not_negated_not_extracted(self):
        query = "NOT to:bob from:alice"
        clauses = _extract_query_clauses(query)
        assert clauses["to"] == []  # negated
        assert clauses["from"] == ["alice"]


# ============================================================================
# TestRelaxQuery
# ============================================================================


class TestRelaxQuery:
    def test_remove_folder(self):
        query = 'folder:"INBOX" from:boss subject:hello'
        clauses = _extract_query_clauses(query)
        result = _relax_query(query, clauses, "folder")
        assert "folder:" not in result
        assert "from:boss" in result
        assert "subject:hello" in result

    def test_remove_to(self):
        query = "to:alice@example.com from:bob"
        clauses = _extract_query_clauses(query)
        result = _relax_query(query, clauses, "to")
        assert "to:" not in result
        assert "from:bob" in result

    def test_remove_date(self):
        query = "date:2024-01-01..2024-06-01 from:alice"
        clauses = _extract_query_clauses(query)
        result = _relax_query(query, clauses, "date")
        assert "date:" not in result
        assert "from:alice" in result

    def test_from_domain_rewrite(self):
        query = "from:user@cam.ac.uk subject:hello"
        clauses = _extract_query_clauses(query)
        result = _relax_query(query, clauses, "from_domain")
        assert "from:cam.ac.uk" in result
        assert "user@" not in result

    def test_from_domain_quoted_not_applied(self):
        query = 'from:"Name <user@cam.ac.uk>" subject:hello'
        clauses = _extract_query_clauses(query)
        result = _relax_query(query, clauses, "from_domain")
        assert result == query  # no-op

    def test_from_domain_bare_domain_not_applied(self):
        query = "from:cam.ac.uk subject:hello"
        clauses = _extract_query_clauses(query)
        result = _relax_query(query, clauses, "from_domain")
        assert result == query  # no @ sign

    def test_negated_not_removed(self):
        query = "-folder:Spam folder:INBOX"
        clauses = _extract_query_clauses(query)
        result = _relax_query(query, clauses, "folder")
        # Only positive folder:INBOX removed, -folder:Spam stays
        assert "-folder:Spam" in result
        assert "folder:INBOX" not in result or "-folder" in result

    def test_no_op_returns_original(self):
        query = "subject:hello from:boss"
        clauses = _extract_query_clauses(query)
        result = _relax_query(query, clauses, "folder")
        assert result == query


# ============================================================================
# TestAutoRelax
# ============================================================================


class TestAutoRelax:
    @patch("mcp_handley_lab.email.notmuch.shared._get_folder_families", return_value={})
    @patch("mcp_handley_lab.email.notmuch.shared._search_emails")
    @patch("mcp_handley_lab.email.notmuch.shared._notmuch_count")
    def test_folder_relaxation(self, mock_count, mock_search, _mock_families):
        mock_search_result = [MagicMock()]
        mock_count.return_value = 5
        mock_search.return_value = mock_search_result

        results, diag = _auto_relax(
            'folder:"INBOX" from:boss',
            10,
            0,
            False,
            "headers",
        )
        assert results == mock_search_result
        assert "folder" in diag
        # Verify relaxed query passed to count/search has folder removed
        relaxed_query = mock_count.call_args[0][0]
        assert "folder:" not in relaxed_query
        assert "from:boss" in relaxed_query
        search_query = mock_search.call_args[0][0]
        assert "folder:" not in search_query

    @patch("mcp_handley_lab.email.notmuch.shared._get_folder_families", return_value={})
    @patch("mcp_handley_lab.email.notmuch.shared._search_emails")
    @patch("mcp_handley_lab.email.notmuch.shared._notmuch_count")
    def test_to_relaxation(self, mock_count, mock_search, _mock_families):
        mock_count.return_value = 3
        mock_search.return_value = [MagicMock()]

        results, diag = _auto_relax(
            "to:alice@example.com subject:hello",
            10,
            0,
            False,
            "headers",
        )
        assert results
        assert "to" in diag
        # Verify to: removed from relaxed query
        relaxed_query = mock_count.call_args[0][0]
        assert "to:" not in relaxed_query
        assert "subject:hello" in relaxed_query

    @patch("mcp_handley_lab.email.notmuch.shared._get_folder_families", return_value={})
    @patch("mcp_handley_lab.email.notmuch.shared._search_emails")
    @patch("mcp_handley_lab.email.notmuch.shared._notmuch_count")
    def test_from_domain_relaxation(self, mock_count, mock_search, _mock_families):
        mock_count.return_value = 2
        mock_search.return_value = [MagicMock()]

        results, diag = _auto_relax(
            "from:user@domain.com subject:hello",
            10,
            0,
            False,
            "headers",
        )
        assert results
        assert "domain" in diag.lower()
        # Verify from: rewritten to domain-only
        relaxed_query = mock_count.call_args[0][0]
        assert "from:domain.com" in relaxed_query
        assert "from:user@domain.com" not in relaxed_query

    @patch("mcp_handley_lab.email.notmuch.shared._get_folder_families", return_value={})
    @patch("mcp_handley_lab.email.notmuch.shared._notmuch_count")
    def test_no_constraints_returns_empty(self, mock_count, _mock_families):
        results, diag = _auto_relax(
            "subject:hello",
            10,
            0,
            False,
            "headers",
        )
        assert results == []
        assert diag is None
        mock_count.assert_not_called()

    @patch("mcp_handley_lab.email.notmuch.shared._get_folder_families", return_value={})
    @patch("mcp_handley_lab.email.notmuch.shared._search_emails")
    @patch("mcp_handley_lab.email.notmuch.shared._notmuch_count")
    def test_stops_at_first_success(self, mock_count, mock_search, _mock_families):
        mock_count.return_value = 5
        mock_search.return_value = [MagicMock()]

        results, diag = _auto_relax(
            'folder:"INBOX" to:alice from:bob',
            10,
            0,
            False,
            "headers",
        )
        assert "folder" in diag  # first match wins
        # Only one count call and one search call (stopped at folder step)
        assert mock_count.call_count == 1
        assert mock_search.call_count == 1

    @patch("mcp_handley_lab.email.notmuch.shared._get_folder_families", return_value={})
    @patch("mcp_handley_lab.email.notmuch.shared._search_emails")
    @patch("mcp_handley_lab.email.notmuch.shared._notmuch_count")
    def test_count_fetch_mismatch_continues(
        self, mock_count, mock_search, _mock_families
    ):
        mock_count.return_value = 5
        # First call returns empty (mismatch), second returns results
        mock_search.side_effect = [[], [MagicMock()]]

        results, diag = _auto_relax(
            'folder:"INBOX" to:alice',
            10,
            0,
            False,
            "headers",
        )
        assert results
        assert "to" in diag  # skipped folder due to mismatch
        # Two count calls (folder then to), two search calls
        assert mock_count.call_count == 2
        assert mock_search.call_count == 2
        # First search was folder-relaxed, second was to-relaxed
        first_search_query = mock_search.call_args_list[0][0][0]
        assert "folder:" not in first_search_query
        assert "to:alice" in first_search_query
        second_search_query = mock_search.call_args_list[1][0][0]
        assert 'folder:"INBOX"' in second_search_query
        assert "to:" not in second_search_query


# ============================================================================
# TestNormalizeFolderQuery
# ============================================================================


class TestNormalizeFolderQuery:
    def test_partial_quoting(self):
        result = _normalize_folder_query('folder:Acct/"Sent Items.2024"')
        assert result == 'folder:"Acct/Sent Items.2024"'

    def test_already_quoted(self):
        query = 'folder:"Acct/Sent Items.2024"'
        assert _normalize_folder_query(query) == query

    def test_bare_without_spaces(self):
        query = "folder:INBOX"
        assert _normalize_folder_query(query) == 'folder:"INBOX"'

    def test_multiple_folders(self):
        query = 'folder:Acct/"Sent Items" OR folder:Acct/"Archive"'
        result = _normalize_folder_query(query)
        assert 'folder:"Acct/Sent Items"' in result
        assert 'folder:"Acct/Archive"' in result

    def test_preserves_operators_and_other_clauses(self):
        query = 'folder:Acct/"Sent Items" OR tag:inbox AND from:boss'
        result = _normalize_folder_query(query)
        assert result == 'folder:"Acct/Sent Items" OR tag:inbox AND from:boss'

    def test_preserves_parentheses(self):
        query = '(folder:Acct/"Sent Items" OR folder:Acct/"Archive") AND from:bob'
        result = _normalize_folder_query(query)
        assert (
            result == '(folder:"Acct/Sent Items" OR folder:"Acct/Archive") AND from:bob'
        )

    def test_negated_folder_preserved(self):
        result = _normalize_folder_query('-folder:Acct/"Sent Items"')
        assert result == '-folder:"Acct/Sent Items"'

    def test_closing_paren_after_folder(self):
        query = '(folder:Acct/"Sent Items") AND from:bob'
        result = _normalize_folder_query(query)
        assert result == '(folder:"Acct/Sent Items") AND from:bob'

    def test_no_whitespace_before_or(self):
        """Adjacent OR without space must not be consumed."""
        result = _normalize_folder_query('folder:Acct/"Sent Items"OR tag:inbox')
        assert "OR" in result
        assert "tag:inbox" in result

    def test_no_whitespace_before_paren(self):
        """Adjacent )AND without space must not be consumed."""
        result = _normalize_folder_query('folder:Acct/"Sent Items")AND from:bob')
        assert ")AND" in result
        assert "from:bob" in result

    def test_mode_full_uses_show_email(self):
        """Auto-relax with non-headers mode calls _show_email."""
        with (
            patch(
                "mcp_handley_lab.email.notmuch.shared._get_folder_families",
                return_value={},
            ),
            patch("mcp_handley_lab.email.notmuch.shared._show_email") as mock_show,
            patch(
                "mcp_handley_lab.email.notmuch.shared._notmuch_count", return_value=3
            ),
        ):
            mock_show.return_value = [MagicMock()]
            results, diag = _auto_relax(
                'folder:"INBOX" from:boss',
                10,
                0,
                False,
                "full",
            )
            assert results
            assert mock_show.called
            show_query = mock_show.call_args[0][0]
            assert "folder:" not in show_query


# ============================================================================
# TestParseQueryTokens
# ============================================================================


class TestParseQueryTokens:
    def test_basic_tokens(self):
        tokens = list(_parse_query_tokens("folder:INBOX from:boss"))
        assert len(tokens) == 2
        assert tokens[0][2] == "folder"
        assert tokens[0][3] == "INBOX"
        assert tokens[1][2] == "from"
        assert tokens[1][3] == "boss"

    def test_quoted_value(self):
        tokens = list(_parse_query_tokens('folder:"Sent Items"'))
        assert len(tokens) == 1
        assert tokens[0][3] == '"Sent Items"'

    def test_inside_parens_not_yielded(self):
        tokens = list(_parse_query_tokens("(folder:INBOX OR from:bob)"))
        assert len(tokens) == 0

    def test_negation_dash(self):
        tokens = list(_parse_query_tokens("-folder:Spam"))
        assert len(tokens) == 1
        assert tokens[0][5] is True  # negated

    def test_negation_not_keyword(self):
        tokens = list(_parse_query_tokens("NOT folder:Spam"))
        assert len(tokens) == 1
        assert tokens[0][5] is True

    def test_negation_lowercase_not(self):
        tokens = list(_parse_query_tokens("not folder:Spam"))
        assert len(tokens) == 1
        assert tokens[0][5] is True

    def test_not_inside_value_not_negated(self):
        # subject:NOT is not a standalone NOT operator
        tokens = list(_parse_query_tokens("subject:NOT folder:Spam"))
        folder_tokens = [t for t in tokens if t[2] == "folder"]
        assert len(folder_tokens) == 1
        # "NOT" is the value of subject:, not a standalone operator
        # The last whitespace-delimited token before folder: is "subject:NOT"
        assert folder_tokens[0][5] is False

    def test_parens_inside_quotes_ignored(self):
        tokens = list(_parse_query_tokens('subject:"status (draft)" folder:INBOX'))
        folder_tokens = [t for t in tokens if t[2] == "folder"]
        assert len(folder_tokens) == 1
        assert folder_tokens[0][3] == "INBOX"

    def test_tab_separated_not(self):
        tokens = list(_parse_query_tokens("NOT\tfolder:Spam"))
        assert len(tokens) == 1
        assert tokens[0][5] is True  # negated via tab-separated NOT
