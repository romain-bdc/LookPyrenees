"""CLI to run LookPyrenees module"""
import argparse
import logging
from pathlib import Path
import sys

from __init__ import __version__
from download import process
#from lookpyrenees import *

__author__ = "Romain Buguet de Chargère"
__copyright__ = "Romain Buguet de Chargère"



# ---- CLI ----
def parse_args(args):
    """Parse command line parameters

    Args:
      args (List[str]): command line parameters as list of strings
          (for example  ``["--help"]``).

    Returns:
      :obj:`argparse.Namespace`: command line parameters namespace
    """
    parser = argparse.ArgumentParser(description="Workflow that download last images of Pyrenees")

    parser.add_argument(dest="zone", help="zone of Pyrenees to view", type=str)
    parser.add_argument(dest='out_path', help='Output dirpath to store Pyrenees image', type=Path)

    parser.add_argument(
        "-p",
        "--pref-provider",
        dest="pref_provider",
        help="Select preferred provider",
        type=str,
        default='cop_dataspace',
    )
    parser.add_argument(
        "-s",
        "--show-results",
        dest="plot_results",
        help="Boolean to view or not search results",
        type=bool,
        default=False,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"ewoc_generate_agera5_yearly {__version__}")

    parser.add_argument(
        "-v",
        "--verbose",
        dest="loglevel",
        help="set loglevel to INFO",
        action="store_const",
        const=logging.INFO,
    )
    parser.add_argument(
        "-vv",
        "--very-verbose",
        dest="loglevel",
        help="set loglevel to DEBUG",
        action="store_const",
        const=logging.DEBUG,
    )

    return parser.parse_args(args)


def setup_logging(loglevel):
    """Setup basic logging

    Args:
      loglevel (int): minimum loglevel for emitting messages
    """
    logformat = "[%(asctime)s] %(levelname)s:%(name)s:%(message)s"
    logging.basicConfig(
        level=loglevel, stream=sys.stdout, format=logformat, datefmt="%Y-%m-%d %H:%M:%S"
    )

def main(args):
    """Download, process and upload agera5 cog file for a year on
    ewoc-aux-data bucket

    Args:
      args (List[str]): command line parameters as list of strings
          (for example  ``["--verbose", "42"]``).
    """
    args = parse_args(args)
    setup_logging(args.loglevel)

    process(zone=args.zone,
            outdir=args.out_path,
            pref_provider=args.pref_provider,
            plot_res=args.plot_results,
            )

def run():
    """Calls :func:`main` passing the CLI arguments extracted from :obj:`sys.argv`
    """
    main(sys.argv[1:])

if __name__ == "__main__":
    run()
