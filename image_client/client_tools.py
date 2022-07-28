#!/usr/bin/env python3
import argparse
import logging
import collection_definitions
from botany_importer import BotanyImporter
import sys
from ichthyology_importer import IchthyologyImporter
from image_client import ImageClient
from botany_purger import BotanyPurger

args = None
logger = None


def parse_command_line():
    parser = argparse.ArgumentParser(
        description=f"""
             Tool to manipulate images on the CAS image server. 
             
             Available collections:
             {[x for x in collection_definitions.COLLECTION_DIRS.keys()]}
             
             Commands: import, search, purge. Collection is mandatory.
             """,
        formatter_class=argparse.RawTextHelpFormatter, add_help=True)

    parser.add_argument('-v', '--verbosity',
                        help='verbosity level. repeat flag for more detail',
                        default=0,
                        dest='verbose',
                        action='count')

    parser.add_argument('collection', help='Collection')

    subparsers = parser.add_subparsers(help='Select search or import mode', dest="subcommand")
    search_parser = subparsers.add_parser('search')
    import_parser = subparsers.add_parser('import')
    purge_parser = subparsers.add_parser('purge')

    search_parser.add_argument('term')

    return parser.parse_args()



def main(args):

    if args.subcommand == 'search':
        image_client = ImageClient()
    elif args.subcommand == 'import':

        if args.collection == "Botany":
             BotanyImporter()
        elif args.collection == "Ichthyology":
            IchthyologyImporter()
    elif args.subcommand == 'purge':
        logger.debug("Purge!")

        if args.collection == "Botany":
            purger = BotanyPurger()
            purger.purge()
    else:
        print(f"Unknown command: {args.subcommand}")





def setup_logging(verbosity: int):
    """
    Set the logging level, between 0 (critical only) to 4 (debug)

    Args:
        verbosity: The level of logging to set

    """
    global logger
    print("setting up logging...")
    logger = logging.getLogger('Client')
    logger.setLevel(logging.DEBUG)  # better to have too much log than not enough
    console_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(name)s — %(levelname)s — %(funcName)s:%(lineno)d - %(message)s")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # with this pattern, it's rarely necessary to propagate the error up to parent
    logger.propagate = False

    if verbosity == 0:
        logger.setLevel(logging.CRITICAL)
    elif verbosity == 1:
        logger.setLevel(logging.ERROR)
    elif verbosity == 2:
        logger.setLevel(logging.WARN)
    elif verbosity == 3:
        logger.setLevel(logging.INFO)
    elif verbosity >= 4:
        logger.setLevel(logging.DEBUG)


def bad_collection():
    if len(sys.argv) == 1:
        print(f"No arguments specified; specify a collection")
    else:
        print(f"Invalid collection: {sys.argv[1]}")
    print(f"Available collections: {[x for x in collection_definitions.COLLECTION_DIRS.keys()]}")
    print(f"Run {sys.argv[0]} --help for more info.")
    print("   Note: command and collection required for detailed help. e.g.:")
    print("   ./image-client.py Botany import --help")
    sys.exit(1)


if __name__ == '__main__':
    # if len(sys.argv) == 1 or sys.argv[1] not in collection_definitions.COLLECTION_DIRS.keys():
    #     bad_collection()
    args = parse_command_line()
    # if args.disable_test:
    #     print("RUNNING IN TEST ONLY MODE. See help to disable.")

    setup_logging(args.verbose)

    logger.debug(f"Starting client...")

    if args.collection not in collection_definitions.COLLECTION_DIRS.keys():
        bad_collection()

    main(args)