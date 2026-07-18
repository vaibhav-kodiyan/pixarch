"""Regression tests for installing the Pixarch SDDM theme with Qt 6."""

from __future__ import annotations

import configparser
import re
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
THEME_DIRECTORY = REPOSITORY_ROOT / "boot/sddm/themes/pixarch_sddm"
THEME_METADATA = THEME_DIRECTORY / "metadata.desktop"
THEME_QML = THEME_DIRECTORY / "Main.qml"
SDDM_CONFIGURATION = REPOSITORY_ROOT / "installation_scripts/theme.conf"
INSTALL_SCRIPT = REPOSITORY_ROOT / "installation_scripts/install.sh"


def read_ini(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(path, encoding="utf-8")
    return parser


def active_shell_source(path: Path) -> str:
    """Return shell source with fully commented lines omitted."""
    return "\n".join(
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )


class SddmThemeMetadataTests(unittest.TestCase):
    def test_theme_declares_the_qt6_greeter(self) -> None:
        self.assertTrue(
            THEME_METADATA.is_file(),
            "SDDM needs metadata.desktop to select the correct Qt greeter",
        )

        metadata = read_ini(THEME_METADATA)
        self.assertTrue(metadata.has_section("SddmGreeterTheme"))
        theme = metadata["SddmGreeterTheme"]

        self.assertEqual(theme.get("Type"), "sddm-theme")
        self.assertEqual(theme.get("Theme-Id"), "pixarch_sddm")
        self.assertEqual(theme.get("Theme-API"), "2.0")
        self.assertEqual(theme.get("MainScript"), "Main.qml")
        self.assertEqual(theme.get("ConfigFile"), "theme.conf")
        self.assertEqual(
            theme.get("QtVersion"),
            "6",
            "QtVersion=6 is required so SDDM does not select its Qt 5 greeter",
        )

    def test_metadata_and_theme_configuration_reference_existing_files(self) -> None:
        self.assertTrue(
            THEME_METADATA.is_file(),
            "Cannot validate theme resources until metadata.desktop exists",
        )

        metadata = read_ini(THEME_METADATA)["SddmGreeterTheme"]
        main_script = THEME_DIRECTORY / metadata.get("MainScript", "")
        config_file = THEME_DIRECTORY / metadata.get("ConfigFile", "")

        self.assertTrue(main_script.is_file(), f"Missing QML entry point: {main_script}")
        self.assertTrue(config_file.is_file(), f"Missing theme config: {config_file}")

        theme_config = read_ini(config_file)
        self.assertTrue(theme_config.has_section("General"))
        for key in ("background", "defaultBackground"):
            background = THEME_DIRECTORY / theme_config["General"].get(key, "")
            self.assertTrue(background.is_file(), f"Missing theme {key}: {background}")


class SddmThemeQmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.theme_source = THEME_QML.read_text(encoding="utf-8")

    def test_connections_use_qt6_function_handlers(self) -> None:
        self.assertNotRegex(
            self.theme_source,
            re.compile(r"^\s*onLogin(?:Succeeded|Failed)\s*:", re.MULTILINE),
            "Qt 6 SDDM themes must not use Qt 5-style Connections handlers",
        )
        self.assertRegex(
            self.theme_source,
            re.compile(r"function\s+onLoginSucceeded\s*\(\s*\)"),
            "The login success handler must use Qt 6 function syntax",
        )
        self.assertRegex(
            self.theme_source,
            re.compile(r"function\s+onLoginFailed\s*\(\s*\)"),
            "The login failure handler must use Qt 6 function syntax",
        )

    def test_theme_assets_are_resolved_to_theme_urls(self) -> None:
        self.assertRegex(
            self.theme_source,
            re.compile(r"source\s*:\s*Qt\.resolvedUrl\s*\(\s*config\.background\s*\)"),
            "Configured backgrounds must be resolved relative to the theme directory",
        )
        self.assertRegex(
            self.theme_source,
            re.compile(
                r"var\s+defaultBackground\s*=\s*Qt\.resolvedUrl\s*\("
                r"\s*config\.defaultBackground\s*\)"
            ),
            "Fallback backgrounds must be resolved relative to the theme directory",
        )
        self.assertRegex(
            self.theme_source,
            re.compile(r"arrowIcon\s*:\s*Qt\.resolvedUrl\s*\(\s*\"angle-down\.png\"\s*\)"),
            "Local SDDM component assets must be resolved relative to the theme directory",
        )


class SddmThemeInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.install_source = active_shell_source(INSTALL_SCRIPT)

    def test_installer_deploys_the_qt6_theme_and_enables_it(self) -> None:
        self.assertRegex(
            self.install_source,
            re.compile(
                r"boot/sddm/themes/pixarch_sddm[^\n]*"
                r"/usr/share/sddm/themes/?"
            ),
            "The installer must deploy the Pixarch theme, not leave the command commented",
        )
        self.assertRegex(
            self.install_source,
            re.compile(
                r"installation_scripts/theme\.conf[^\n]*"
                r"/etc/sddm\.conf\.d/[^\s]+"
            ),
            "The installer must enable the theme through an SDDM config drop-in",
        )

    def test_installer_does_not_replace_the_global_sddm_configuration(self) -> None:
        direct_global_config = re.compile(r"/etc/sddm\.conf(?:\s|$)", re.MULTILINE)
        self.assertNotRegex(
            self.install_source,
            direct_global_config,
            "Theme installation must not overwrite /etc/sddm.conf",
        )

    def test_installed_configuration_selects_the_pixarch_theme(self) -> None:
        configuration = read_ini(SDDM_CONFIGURATION)
        self.assertTrue(configuration.has_section("Theme"))
        self.assertEqual(configuration["Theme"].get("Current"), "pixarch_sddm")


if __name__ == "__main__":
    unittest.main()
