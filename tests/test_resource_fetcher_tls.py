import contextlib
import io
import ssl
import sys
import types
import unittest
from unittest import mock

import repo_path  # noqa: F401
from Scripts import resource_fetcher


class FakeContext:
    def __init__(self, ca_count=1):
        self.ca_count = ca_count

    def cert_store_stats(self):
        return {"x509": self.ca_count, "crl": 0, "x509_ca": self.ca_count}


def fake_certifi(path):
    module = types.ModuleType("certifi")
    module.where = lambda: path
    return module


class TLSContextTest(unittest.TestCase):
    def setUp(self):
        resource_fetcher.ResourceFetcher._unverified_warning_shown = False

    def tearDown(self):
        resource_fetcher.ResourceFetcher._unverified_warning_shown = False

    def make(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            fetcher = resource_fetcher.ResourceFetcher()
        return fetcher, output.getvalue()

    def test_certifi_bundle_first(self):
        context = FakeContext()
        with mock.patch.dict(sys.modules, {"certifi": fake_certifi("certifi-bundle.pem")}):
            with mock.patch.object(resource_fetcher.ssl, "create_default_context", return_value=context) as create:
                fetcher, output = self.make()
        self.assertIs(fetcher.ssl_context, context)
        create.assert_called_once_with(cafile="certifi-bundle.pem")
        self.assertEqual(output, "")

    def test_system_store_without_certifi(self):
        context = FakeContext()
        with mock.patch.dict(sys.modules, {"certifi": None}):
            with mock.patch.object(resource_fetcher.ssl, "create_default_context", return_value=context) as create:
                fetcher, output = self.make()
        self.assertIs(fetcher.ssl_context, context)
        create.assert_called_once_with()
        self.assertEqual(output, "")

    def test_system_store_when_certifi_bundle_fails(self):
        context = FakeContext()

        def create(cafile=None):
            if cafile:
                raise FileNotFoundError(cafile)
            return context

        with mock.patch.dict(sys.modules, {"certifi": fake_certifi("missing.pem")}):
            with mock.patch.object(resource_fetcher.ssl, "create_default_context", side_effect=create):
                fetcher, output = self.make()
        self.assertIs(fetcher.ssl_context, context)
        self.assertEqual(output, "")

    def test_empty_store_with_capath_is_still_used(self):
        context = FakeContext(ca_count=0)
        paths = mock.Mock(capath=resource_fetcher.os.path.dirname(resource_fetcher.__file__))
        with mock.patch.dict(sys.modules, {"certifi": None}):
            with mock.patch.object(resource_fetcher.ssl, "create_default_context", return_value=context):
                with mock.patch.object(resource_fetcher.ssl, "get_default_verify_paths", return_value=paths):
                    fetcher, output = self.make()
        self.assertIs(fetcher.ssl_context, context)
        self.assertEqual(output, "")

    def test_unverified_last_with_one_warning(self):
        unverified = object()
        with mock.patch.dict(sys.modules, {"certifi": None}):
            with mock.patch.object(resource_fetcher.ssl, "create_default_context", side_effect=ssl.SSLError("no store")):
                with mock.patch.object(resource_fetcher.ssl, "_create_unverified_context", return_value=unverified):
                    first, first_output = self.make()
                    second, second_output = self.make()
        self.assertIs(first.ssl_context, unverified)
        self.assertIs(second.ssl_context, unverified)
        self.assertIn("cannot be verified", first_output)
        self.assertEqual(first_output.count("Warning:"), 1)
        self.assertEqual(second_output, "")

    def test_unverified_when_store_is_empty(self):
        unverified = object()
        paths = mock.Mock(capath=None)
        with mock.patch.dict(sys.modules, {"certifi": None}):
            with mock.patch.object(resource_fetcher.ssl, "create_default_context", return_value=FakeContext(ca_count=0)):
                with mock.patch.object(resource_fetcher.ssl, "get_default_verify_paths", return_value=paths):
                    with mock.patch.object(resource_fetcher.ssl, "_create_unverified_context", return_value=unverified):
                        fetcher, output = self.make()
        self.assertIs(fetcher.ssl_context, unverified)
        self.assertIn("no CA certificates found", output)

    def test_real_context_verifies_without_noise(self):
        with mock.patch.dict(sys.modules, {"certifi": None}):
            fetcher, output = self.make()
        self.assertNotIn("Failed to create SSL context", output)
        if output == "":
            self.assertEqual(fetcher.ssl_context.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(fetcher.ssl_context.check_hostname)

    @unittest.skipUnless(sys.platform == "win32", "the Windows certificate store only exists on Windows")
    def test_windows_store_is_loaded_without_certifi(self):
        with mock.patch.dict(sys.modules, {"certifi": None}):
            fetcher, output = self.make()
        self.assertEqual(output, "")
        self.assertGreater(fetcher.ssl_context.cert_store_stats()["x509_ca"], 0)


if __name__ == "__main__":
    unittest.main()
