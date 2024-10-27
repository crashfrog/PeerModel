import click
from peermodel import with_database

import logging


## https://click.palletsprojects.com/en/8.1.x/

## @click.group()
## @click.argument()
## @click.option('-s', '--string-to-echo', 'string')
## @click.option('--n', default=1, show_default=True)
## @click.option("--rr", is_flag=True, show_default=True, default=False, help="Greet the world.")
## @click.option("--br", is_flag=True, show_default=True, default=True, help="Add a thematic break")
## @click.option('--shout/--no-shout', default=False)


@click.group()
def cli():
    "Management interface for PeerModel identity and rings."
    pass

@cli.command()
def init():
    "Initialize your identity"
    pass


@cli.group()
def ring():
    "Commands for managing rings"
    pass

@ring.command("list")
@with_database
def ring_list(db):
    "List rings you're a member of"
    pass

rarg = click.argument("ring") # ring argument, used by a lot of commands

@ring.command("create")
@with_database
def site_init(db):
    "Initalize keys for a new ring for an existing application"
    db.site.initialize()

@ring.command("invite")
@rarg
@click.argument("identity")
@with_database
def site_invite(db, ring, identity):
    "Invite new user into the ring"
    pass

@ring.command("review")
@with_database
def site_requests(db):
    "Review existing access requests"
    pass

@ring.command("approve")
@click.argument("request")
@with_database
def site_approve(db, request):
    "Approve membership or guest access request"
    pass

@ring.command("revoke")
@rarg
@click.argument("identity")
@with_database
def site_revoke(db, ring, identity):
    "Revoke ring guest access and regenerate keys"
    pass

@ring.command("regenerate")
@rarg
@with_database
def site_regenerate(db, ring):
    "Regenerate ring keys"
    pass




def build_cli(
        app_name="my app",
):
    "CLI Builder for applications using PeerModel"

    @click.group(help=f"Management interface for the {app_name} database, using PeerModel.")
    @click.version_option(package_name="peermodel", message="%(prog)s %(version)s")
    @click.option("-v", "--verbose", count=True)
    def cli(verbose=0):
        log_level = {0:60, 1:30, 2:20, 3:10}[verbose]
        logging.basicConfig(level=log_level,
                            format='[%(asctime)s][%(name)-12s][%(levelname)-8s] %(message)s',
                            datefmt='%m-%d %H:%M')
        


    @ring.group()
    @rarg
    def guest(ring):
        "Commands for managing ring guests, invited read-only users of an app"
        pass

    @guest.command("invite")
    @with_database
    @rarg
    def guest_invite(db, ring):
        "Invite new user into the guest group"
        pass

    @guest.command("review")
    @with_database
    @rarg
    def guest_requests(db, ring):
        "Review existing access requests"
        pass

    @guest.command("approve")
    @with_database
    def guest_approve(db, ring):
        "Approve request"
        pass

    @guest.command("revoke")
    @with_database
    def guest_revoke(db, ring):
        "Revoke guest access and regenerate site keys"
        pass


    @cli.command("list")
    @with_database
    def show(db):
        "Summarize records accessible through your credentials"
        pass

    @cli.command("index")
    @with_database
    def index(db):
        "Build or re-build the searchable records index"
        pass

    @cli.command()
    @click.argument("content")
    @click.option("-r", "--ring", default=None)
    @with_database
    def create(db, content, ring=None):
        "Create a record"
        pass

    @cli.command()
    @click.argument("id")
    @click.option("-r", "--ring", default=None)
    @with_database
    def retrieve(db, id, ring=None):
        "Retrieve record by ID"
        pass

    @cli.command()
    @click.argument("id")
    @click.argument("content")
    @click.option("-r", "--ring", default=None)
    @with_database
    def update(db, id, content, ring=None):
        "Update a record"
        pass

    @cli.command()
    @click.argument("id")
    @click.option("-r", "--ring", default=None)
    @with_database
    def delete(db, id, ring=None):
        "Mark a record as retracted"
        pass

    @cli.command()
    @click.argument("id")
    @click.option("-r", "--ring", default=None)
    @with_database
    def undelete(db, id, ring=None):
        "Unmark a record as retracted"
        pass

    @cli.command()
    @click.argument("id")
    @click.argument("tag")
    @with_database
    def tag(db, id, tag=""):
        "Add a public tag to a record"
        pass

    @cli.command()
    @click.argument("id")
    @click.argument("tag")
    @with_database
    def untag(db, id, tag=""):
        "Remove a public tag from a record"
        pass

    @cli.command()
    @click.argument("id")
    @with_database
    def publish(db, id):
        "Enable anonymous, unauthenticated view of a record"
        pass


    @cli.group()
    def start():
        "Start the peer service"
        pass

    @start.command()
    def events():
        "Start the event listener service"
        pass

    @cli.group()
    def stop():
        "Stop the peer service"
        pass

    @stop.command()
    def events():
        "Stop the event listener service"
        pass



    return cli





if __name__ == '__main__':
    cli()