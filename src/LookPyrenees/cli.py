"""CLI to run LookPyrenees module"""
import argparse
import logging
import sys
from pathlib import Path

from LookPyrenees.download import check_old_files, process

__author__ = "Romain Buguet de Chargère"
__copyright__ = "Romain Buguet de Chargère"
__version__ = "0.0.1"

ALL_ZONES = ["3seigneurs", "carlit", "orlu", "rulhe_nerassol"]


# ---- CLI ----
def parse_args(args):
    """Parse command line parameters

    Args:
      args (List[str]): command line parameters as list of strings
          (for example  ``["--help"]``).

    Returns:
      :obj:`argparse.Namespace`: command line parameters namespace
    """
    parser = argparse.ArgumentParser(
        description="Workflow that download last images of Pyrenees"
    )

    parser.add_argument("-z",
                        "--zone",
                        dest="zone",
                        help="zone of Pyrenees to view, if no specified download all zones",
                        type=str,
                        default="all")

    parser.add_argument(
        "-o",
        "--out-path",
        dest="out_path",
        help="Output dirpath to store Pyrenees image",
        type=Path,
        default="./data"
    )

    parser.add_argument(
        "-p",
        "--pref-provider",
        dest="pref_provider",
        help="Select preferred provider",
        type=str,
        default="cop_dataspace",
    )
    parser.add_argument(
        "-b",
        "--bucket-name",
        dest="bucket_name",
        help="Select the bucket name",
        type=str,
        default=None,
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
        "--version", action="version", version=f"Look Pyrenees version : {__version__}"
    )

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
    """Download and crop area of interest of pyrenees to monitor snow

    Args:
      args (List[str]): command line parameters as list of strings
          (for example  ``["--verbose", "42"]``).
    """
    args = parse_args(args)
    setup_logging(args.loglevel)

    if args.zone == "all":
        zones_list = ALL_ZONES
    else:
        zones_list = [args.zone]

    Path(args.out_path).mkdir(parents=True, exist_ok=True)

    for zone in zones_list:

        logging.info(f"Downloading {zone} zone")

        process(
            zone=zone,
            outdir=args.out_path,
            pref_provider=args.pref_provider,
            plot_res=args.plot_results,
            bucket=args.bucket_name
        )

    check_old_files(args.out_path)


def run():
    """Calls :func:`main` passing the CLI arguments extracted from :obj:`sys.argv`"""
    main(sys.argv[1:])


if __name__ == "__main__":
    run()
