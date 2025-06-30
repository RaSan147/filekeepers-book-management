"""Network system utilities including URL parsing, HTML processing, and path manipulation."""
import socket
from re import compile as re_compile
from re import sub as re_sub
from typing import Any, Dict, Optional, OrderedDict, Union
from urllib.parse import ParseResult, urljoin, urlparse

from bs4 import BeautifulSoup as bs
from bs4 import FeatureNotFound as bs_FeatureNotFound
from bs4 import Tag

# Default parser for BeautifulSoup
_PARSER = 'lxml'
try:
	bs('<br>', _PARSER)
except bs_FeatureNotFound:
	_PARSER = 'html.parser'


class CallableDict(dict):
	"""A dictionary that can be called as a function to check key existence."""
	def __call__(self, *keys):
		return all(key in self for key in keys)


class LimitedDict(OrderedDict, CallableDict):
	"""An ordered dictionary with a size limit."""
	def __init__(self, *args, max_size=0, **kwargs):
		self._max_size = max_size
		super().__init__(*args, **kwargs)

	def __setitem__(self, key, value):
		super().__setitem__(key, value)
		if self._max_size > 0 and len(self) > self._max_size:
			self.popitem(False)

class WebURL:
	"""Robust URL parsing with strict validation."""
	
	# Common URL schemes
	VALID_SCHEMES = {'http', 'https', 'ftp', 'ftps', 'sftp', 'ws', 'wss'}
	URL_REGEX = re_compile(
		r'^([a-zA-Z][a-zA-Z0-9+.-]*:)?//'  # Scheme
		r'([^/@]+@)?'  # User info
		r'([^/:?#]+)'  # Host
		r'(:[0-9]+)?'  # Port
		r'([/][^?#]*)?'  # Path
		r'(\?[^#]*)?'  # Query
		r'(#.*)?$'  # Fragment
	)

	DEFAULT_FACTS = {
		'is_link': False,
		'is_valid': False,
		'url': None,
		'scheme': None,
		'netloc': None,
		'path': None,
		'query': None,
		'fragment': None,
		'username': None,
		'password': None,
		'hostname': None,
		'port': None,
		'homepage': None,
		'has_homepage': False,
		'after_homepage': False,
		'needs_scheme': False,
		'is_absolute': False,
		'is_ip': False,
		'is_ipv6': False,
		'is_localhost': False,
		'is_private': False
	}

	
	# Cache for parsed URL information
	_LINK_FACTS = LimitedDict(max_size=1000)


	@classmethod
	def _looks_like_url(cls, text: str) -> bool:
		"""Quick check if text resembles a URL."""
		return (
			'://' in text or  # Contains scheme
			text.startswith(('//', '/')) or  # Protocol-relative or absolute path
			cls.URL_REGEX.match(text) is not None
		)

	@staticmethod
	def _is_valid_hostname(hostname: Union[str, None]) -> bool:
		"""Validate hostname according to RFC standards."""
		if not hostname or len(hostname) > 253:
			return False
			
		# Check for IPv6 addresses
		if hostname.startswith('[') and hostname.endswith(']'):
			try:
				socket.inet_pton(socket.AF_INET6, hostname[1:-1])
				return True
			except (socket.error, ValueError):
				return False
				
		# Check for IPv4 addresses
		try:
			socket.inet_aton(hostname)
			return True
		except socket.error:
			pass
			
		# Check domain name structure
		if '.' not in hostname and hostname != 'localhost':
			return False
			
		# Validate each label
		for label in hostname.split('.'):
			if not label or len(label) > 63:
				return False
			if not re_compile(r'^[a-zA-Z0-9-]+$').match(label):
				return False
			if label.startswith('-') or label.endswith('-'):
				return False
				
		return True

	@classmethod
	def _build_facts(cls, parsed, original_url: str) -> Dict[str, Any]:
		"""Build comprehensive URL facts dictionary."""
		hostname = parsed.hostname
		port = parsed.port
		netloc = parsed.netloc
		
		# Build homepage (scheme + netloc)
		homepage = None
		if parsed.scheme and netloc:
			homepage = f"{parsed.scheme}://{hostname}"
			if port:
				if (parsed.scheme == 'http' and port != 80) or (parsed.scheme == 'https' and port != 443):
					homepage += f":{port}"
			
		# Get network facts
		net_facts = cls._get_network_facts(hostname) if hostname else {}
		
		return {
			'is_link': True,
			'is_valid': True,
			'url': original_url,
			'scheme': parsed.scheme,
			'netloc': netloc,
			'path': parsed.path,
			'query': parsed.query,
			'fragment': parsed.fragment,
			'username': parsed.username,
			'password': parsed.password,
			'hostname': hostname,
			'port': str(port) if port else None,
			'homepage': homepage,
			'has_homepage': homepage is not None,
			'after_homepage': parsed.path.startswith('/'),
			'needs_scheme': original_url.startswith('//'),
			'is_absolute': bool(parsed.scheme and netloc),
			**net_facts
		}

	@staticmethod
	def _get_network_facts(hostname: str) -> Dict[str, Any]:
		"""Get network-related facts about the host."""
		facts = {
			'is_ip': False,
			'is_ipv6': False,
			'is_localhost': False,
			'is_private': False
		}
		
		# Check for localhost
		if hostname == 'localhost':
			facts.update({
				'is_localhost': True,
				'is_private': True
			})
			return facts
			
		# Check for IP addresses
		try:
			if ':' in hostname:  # IPv6
				socket.inet_pton(socket.AF_INET6, hostname)
				facts.update({
					'is_ip': True,
					'is_ipv6': True
				})
			else:  # IPv4
				socket.inet_aton(hostname)
				facts['is_ip'] = True
				
			# Check for private IP ranges
			if hostname.startswith(('10.', '192.168.')) or \
			   hostname.startswith('172.') and 16 <= int(hostname.split('.')[1]) <= 31:
				facts['is_private'] = True
				
		except (socket.error, ValueError):
			pass
			
		return facts

	
	@classmethod
	def parse_url(cls, url: str) -> Optional[Dict[str, Any]]:
		"""Strict URL parsing with comprehensive validation."""
		if isinstance(url, bytes):
			try:
				url = url.decode('utf-8')
			except UnicodeDecodeError:
				return cls.DEFAULT_FACTS.copy()
				
		if not isinstance(url, str) or not url.strip():
			return cls.DEFAULT_FACTS.copy()

		if url in cls._LINK_FACTS:
			return cls._LINK_FACTS[url]

		try:
			parsed = urlparse(url)
			facts = cls._build_facts(parsed, url)
			
			# Special handling for protocol-relative URLs
			if url.startswith('//'):
				facts['is_link'] = True
				facts['is_valid'] = bool(parsed.netloc)  # Valid if has netloc
				facts['needs_scheme'] = True
			
			# Validate the parsed URL
			if not cls._is_valid_parsed_url(parsed, url):
				if not (url.startswith('/') or url.startswith('//')):
					return cls.DEFAULT_FACTS.copy()
				facts['is_valid'] = False
			
			cls._LINK_FACTS[url] = facts
			return facts
			
		except (ValueError, AttributeError):
			return cls.DEFAULT_FACTS.copy()

	@classmethod
	def _is_valid_parsed_url(cls, parsed:ParseResult, original_url: str) -> bool:
		"""Validate parsed URL components with special cases."""
		# Protocol-relative URLs are valid if they have netloc
		if original_url.startswith('//'):
			return bool(parsed.netloc)
			
		# Absolute paths are valid links
		if original_url.startswith('/'):
			return True
			
		# Regular URLs need scheme and netloc
		if not parsed.scheme or not parsed.netloc:
			return False
			
		# Validate hostname if present
		if parsed.netloc and not cls._is_valid_hostname(parsed.hostname):
			return False
			
		return True


def html_to_text(html_content: str) -> str:
	"""Convert HTML content to plain text with basic formatting."""
	html_content = html_content.replace("<br>", "\n").replace("<br/>", "\n")
	html_content = html_content.replace("&emsp;", "\t")
	return bs(html_content, _PARSER).get_text()


def text_to_html(plain_text: str) -> str:
	"""Convert plain text to simple HTML formatting."""
	plain_text = plain_text.replace("\n", "<br>")
	plain_text = plain_text.replace("\t", "&emsp;")
	return plain_text


def get_parent_directory(directory: str) -> str:
	"""Get the parent directory of a given directory path."""
	if directory.endswith('/'):
		directory = directory[:-1]
	parts = directory.split('/')
	if len(parts) <= 1:
		return '/'
	parent_parts = parts[:-1]
	if parent_parts == ['']:
		return '/'
	return '/'.join(parent_parts) + '/'


def resolve_relative_link(relative_link: str, current_link: str, homepage: Optional[str]=None) -> str:
	"""Convert a relative link to an absolute URL."""
	base = current_link
	if not homepage:
		parsed = WebURL.parse_url(current_link)
		homepage = parsed['homepage'] if parsed and parsed['homepage'] else None
	
	if homepage:
		parsed = urlparse(current_link)
		if not parsed.scheme:
			base = urljoin(homepage, current_link)
	
	return urljoin(base, relative_link)

# def resolve_relative_link(relative_link: str, current_link: str, homepage: Optional[str]=None) -> str:
#     """Convert a relative link to an absolute URL."""
#     # If we have a homepage and the current link is relative, use homepage as base
#     if homepage:
#         parsed = urlparse(current_link)
#         if not parsed.scheme and not parsed.netloc:  # current_link is relative
#             current_link = urljoin(homepage, current_link)
    
#     return urljoin(current_link, relative_link)

def tag_to_absolute_url(tag: Tag, attr: str, current_url: str, base_url: Optional[str]=None, default_return:Any=None) -> Optional[str]:
	"""
	Convert a tag's attribute to an absolute URL.
	This is used to resolve relative links in the HTML.
	"""
	if not tag or not attr:
		return None
	
	attr_value = tag.get(attr)
	if attr_value is None:
		return default_return
	if attr_value.startswith(('#', 'javascript:')):
		return default_return

	return resolve_relative_link(
		attr_value, current_url, base_url
	)


def get_homepage(url: str) -> Optional[str]:
	"""Extract the homepage using robust parsing."""
	facts = WebURL.parse_url(url)
	return facts['homepage'] if facts else None


def remove_noscript(content: str) -> str:
	"""Remove <noscript> tags and their content from HTML."""
	if isinstance(content, bytes):
		if b'<noscript>' in content:
			return re_sub(b"(?i)(?:<noscript>)(?:.|\n)*?(?:</noscript>)", b'', content)
	elif isinstance(content, str):
		if '<noscript>' in content:
			return re_sub("(?i)(?:<noscript>)(?:.|\n)*?(?:</noscript>)", '', content)
	return content


# Global instance for backward compatibility
web_url = WebURL()



if __name__ == "__main__":
	# Example usage
	url = "http://example.com/path/to/resource?query=1#fragment"
	print(web_url.parse_url(url))

	not_url = "This is not a URL"
	print(web_url.parse_url(not_url))

	half_url = "//example.com/path/to/resource"
	print(web_url.parse_url(half_url))
	
	html = "<div><noscript>JS required</noscript>Content</div>"
	print(remove_noscript(html))
	
	text = "Hello\nWorld\t!"
	print(text_to_html(text))
	print(html_to_text("<p>Hello<br>World</p>"))
	
	print(get_parent_directory("/path/to/dir/"))
	print(resolve_relative_link("page2.html", "http://site.com/page1.html", "http://site.com"))
	print(get_homepage("http://example.com/path/to/resource?query=1#fragment"))
	print(remove_noscript("<div><noscript>JS required</noscript>Content</div>"))