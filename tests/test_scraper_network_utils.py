import pytest
from scraper.network_utils import (
    CallableDict,
    LimitedDict,
    WebURL,
    web_url,
    html_to_text,
    text_to_html,
    get_parent_directory,
    resolve_relative_link,
    get_homepage,
    remove_noscript,
    tag_to_absolute_url
)

def assert_equal(a, b, Note=""):
    """Helper function to assert equality."""
    assert a == b, f"Expected {a} to equal {b}" + ( f" ({Note})" if Note else "")

# Test CallableDict
class TestCallableDict:
    def test_init_and_call(self):
        cd = CallableDict(a=1, b=2)
        assert cd('a') is True
        assert cd('a', 'b') is True
        assert cd('c') is False
        assert cd('a', 'c') is False

    def test_dict_functionality(self):
        cd = CallableDict()
        cd['key'] = 'value'
        assert cd['key'] == 'value'
        assert 'key' in cd
        assert cd('key') is True

# Test LimitedDict
class TestLimitedDict:
    def test_size_limit(self):
        ld = LimitedDict(max_size=2)
        ld['a'] = 1
        ld['b'] = 2
        assert len(ld) == 2
        ld['c'] = 3  # Should remove 'a'
        assert len(ld) == 2
        assert 'a' not in ld
        assert 'b' in ld
        assert 'c' in ld

    def test_unlimited(self):
        ld = LimitedDict()  # max_size=0 by default
        for i in range(100):
            ld[i] = i
        assert len(ld) == 100

    def test_ordered_behavior(self):
        ld = LimitedDict(max_size=3)
        ld['a'] = 1
        ld['b'] = 2
        ld['c'] = 3
        # 'a' should be popped first when we add 'd'
        ld['d'] = 4
        assert 'a' not in ld
        assert 'b' in ld

# Test WebRegex
class TestWebRegex:
    @pytest.mark.parametrize("url,expected", [
        ("http://example.com", True),
        ("https://user:pass@example.com:8080/path?query=1#frag", True),
        ("//example.com", True),
        ("/path/to/resource", True),
        ("not a url", False),
        ("ftp://example.com", True),
    ])
    def test_parse_url(self, url, expected):
        facts = web_url.parse_url(url)
        assert_equal(facts['is_link'], expected, url)

    def test_link_facts_cache(self):
        url = "http://example.com"
        facts1 = web_url.parse_url(url)
        facts2 = web_url.parse_url(url)
        assert facts1 is facts2  # Should be same cached object

    def test_link_facts_components(self):
        url = "https://user:pass@example.com:8080/path/to?query=1#fragment"
        facts = web_url.parse_url(url)
        assert facts['scheme'] == 'https'
        assert facts['username'] == 'user'
        assert facts['password'] == 'pass'
        assert facts['hostname'] == 'example.com'
        assert facts['port'] == '8080'
        assert facts['path'] == '/path/to'
        assert facts['query'] == 'query=1'
        assert facts['fragment'] == 'fragment'
        assert facts['is_absolute'] is True

# Test HTML/text conversion
class TestHtmlTextConversion:
    def test_html_to_text(self):
        html = "<p>Hello<br>World</p>"
        assert html_to_text(html) == "Hello\nWorld"

    def test_text_to_html(self):
        text = "Hello\nWorld"
        assert text_to_html(text) == "Hello<br>World"

    def test_html_to_text_with_tabs(self):
        html = "First&emsp;Second"
        assert html_to_text(html) == "First\tSecond"

    def test_text_to_html_with_tabs(self):
        text = "First\tSecond"
        assert text_to_html(text) == "First&emsp;Second"

# Test path utilities
class TestPathUtilities:
    @pytest.mark.parametrize("directory,expected", [
        ("/path/to/dir/", "/path/to/"),
        ("/path/to/dir", "/path/to/"),
        ("/path/", "/"),
        ("/path", "/"),
        ("/", "/"),
        ("dir/", "/"),
        ("dir", "/"),
    ])
    def test_get_parent_directory(self, directory, expected):
        assert get_parent_directory(directory) == expected

    @pytest.mark.parametrize("relative,current,homepage,expected", [
        ("page2.html", "http://site.com/page1.html", None, "http://site.com/page2.html"),
        ("/about", "http://site.com/blog/", None, "http://site.com/about"),
        ("../img.jpg", "http://site.com/blog/post/", None, "http://site.com/blog/img.jpg"),
        ("page2.html", "/blog/", "http://site.com", "http://site.com/blog/page2.html"),
        ("//other.com/img.jpg", "http://site.com", None, "http://other.com/img.jpg"),
    ])
    def test_resolve_relative_link(self, relative, current, homepage, expected):
        result = resolve_relative_link(relative, current, homepage)
        assert result == expected

    @pytest.mark.parametrize("url,expected", [
        ("http://example.com/path", "http://example.com"),
        ("https://user:pass@example.com:8080/path", "https://example.com:8080"),
        ("/path/to/resource", None),
        ("//example.com/path", None),
        ("not a url", None),
    ])
    def test_get_homepage(self, url, expected):
        assert_equal(get_homepage(url), expected, f"Homepage for {url}\n{web_url.parse_url(url)}")

# Test noscript removal
class TestNoscriptRemoval:
    def test_remove_noscript_str(self):
        html = "<div><noscript><p>JS required</p></noscript>Content</div>"
        assert remove_noscript(html) == "<div>Content</div>"

    def test_remove_noscript_bytes(self):
        html = b"<div><noscript><p>JS required</p></noscript>Content</div>"
        assert remove_noscript(html) == b"<div>Content</div>"

    def test_remove_noscript_no_change(self):
        html = "<div>Content</div>"
        assert remove_noscript(html) == html
        html_bytes = b"<div>Content</div>"
        assert remove_noscript(html_bytes) == html_bytes

    def test_remove_multiple_noscript(self):
        html = """<div>
<noscript>First</noscript>
Content
<noscript>Second</noscript>
More
        </div>"""
        expected = """<div>

Content

More
        </div>"""
        assert_equal(remove_noscript(html), expected)

# Test tag_to_absolute_url
class TestTagToAbsoluteUrl:
    @pytest.fixture
    def mock_tag(self):
        class MockTag:
            def __init__(self, attrs=None):
                self.attrs = attrs or {}
            
            def get(self, attr):
                return self.attrs.get(attr)
        
        return MockTag

    def test_none_tag_or_attr(self, mock_tag):
        # Test None tag
        assert tag_to_absolute_url(None, "href", "http://example.com") is None
        # Test None attr
        tag = mock_tag({"href": "/about"})
        assert tag_to_absolute_url(tag, None, "http://example.com") is None
        # Test empty attr
        assert tag_to_absolute_url(tag, "", "http://example.com") is None

    def test_missing_attribute(self, mock_tag):
        tag = mock_tag()
        assert tag_to_absolute_url(tag, "href", "http://example.com") is None

    def test_skip_special_links(self, mock_tag):
        # Test hash links
        tag = mock_tag({"href": "#section"})
        assert tag_to_absolute_url(tag, "href", "http://example.com") is None
        # Test javascript links
        tag = mock_tag({"href": "javascript:alert(1)"})
        assert tag_to_absolute_url(tag, "href", "http://example.com") is None

    def test_resolve_relative_links(self, mock_tag):
        # Test relative path
        tag = mock_tag({"href": "/about"})
        assert tag_to_absolute_url(tag, "href", "http://example.com") == "http://example.com/about"
        # Test relative file
        tag = mock_tag({"src": "image.jpg"})
        assert tag_to_absolute_url(tag, "src", "http://example.com/blog/") == "http://example.com/blog/image.jpg"
        # Test parent directory
        tag = mock_tag({"href": "../page.html"})
        assert tag_to_absolute_url(tag, "href", "http://example.com/blog/post/") == "http://example.com/blog/page.html"

    def test_preserve_absolute_links(self, mock_tag):
        # Test absolute URL
        tag = mock_tag({"href": "http://other.com/about"})
        assert tag_to_absolute_url(tag, "href", "http://example.com") == "http://other.com/about"
        # Test protocol-relative URL
        tag = mock_tag({"src": "//cdn.example.com/image.jpg"})
        assert tag_to_absolute_url(tag, "src", "http://example.com") == "http://cdn.example.com/image.jpg"

    def test_with_base_url(self, mock_tag):
        # Test with current_url overriding base_url
        tag = mock_tag({"href": "/about"})
        assert tag_to_absolute_url(tag, "href", "http://example.com/blog/", "http://base.com") == "http://example.com/about"
        # Test with base_url when current_url is relative
        tag = mock_tag({"href": "page2.html"})
        assert tag_to_absolute_url(tag, "href", "/blog/", "http://base.com") == "http://base.com/blog/page2.html"