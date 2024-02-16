import click
from peermodel import with_database

import logging


## https://click.palletsprojects.com/en/8.1.x/

## @click.group()
## @click.argument()
## @click.option('-s', '--string-to-echo', 'string')
## @click.option('--n', default=1, show_default=True)
## @click.option("--gr", is_flag=True, show_default=True, default=False, help="Greet the world.")
## @click.option("--br", is_flag=True, show_default=True, default=True, help="Add a thematic break")
## @click.option('--shout/--no-shout', default=False)

def build_cli(
        app_name="my app",
):

    @click.group(help=f"Management interface for the {app_name} database, using PeerModel.")
    @click.version_option(package_name="peermodel", message="%(prog)s %(version)s")
    @click.option("-v", "--verbose", count=True)
    def cli(verbose=0):
        log_level = {0:60, 1:30, 2:20, 3:10}[verbose]
        logging.basicConfig(level=log_level,
                            format='[%(asctime)s][%(name)-12s][%(levelname)-8s] %(message)s',
                            datefmt='%m-%d %H:%M')
        
    @cli.command()
    @with_database
    def init(db, ):
        "Initialize your identity"
        db.initialize_identity()
        
    @cli.group()
    def site():
        "Commands for managing site groups"
        pass

    @site.command("create")
    @click.option("-g", "--site-group", "site_group_name")
    @with_database
    def site_init(db, site_group_name=None):
        "Initalize keys for a new site group for an existing application"
        db.site.initialize(site_group_name)

    @site.command("invite")
    @click.option("-g", "--site-group", "site_group_name")
    @with_database
    def site_invite(db, site_group_name=None):
        "Invite new user into the site group"
        pass

    @site.command("review")
    @click.option("-g", "--site-group", "site_group_name")
    @with_database
    def site_requests(db, site_group_name=None):
        "Review existing access requests"
        pass

    @site.command("approve")
    @click.option("-g", "--site-group", "site_group_name")
    @with_database
    def site_approve(db, site_group_name=None):
        "Approve request"
        pass

    @site.command("revoke")
    @click.option("-g", "--site-group", "site_group_name")
    @with_database
    def site_revoke(db, site_group_name=None):
        "Revoke site group access and regenerate site keys"
        pass

    @site.command("regenerate")
    @click.option("-g", "--site-group", "site_group_name")
    @with_database
    def site_regenerate(db, site_group_name=None):
        "Regenerate site keys"
        pass

    @site.group()
    @click.option("-g", "--site-group", "site_group_name")
    def guest():
        "Commands for managing site guests, invited read-only users"
        pass

    @guest.command("invite")
    @with_database
    def guest_invite(db, ):
        "Invite new user into the guest group"
        pass

    @guest.command("review")
    @with_database
    def guest_requests(db, ):
        "Review existing access requests"
        pass

    @guest.command("approve")
    @with_database
    def guest_approve(db, ):
        "Approve request"
        pass

    @guest.command("revoke")
    @with_database
    def guest_revoke(db, ):
        "Revoke guest access and regenerate site keys"
        pass


    @cli.command("list")
    @with_database
    def show(db):
        "List records accessible through your credentials"
        pass

    @cli.command("index")
    @with_database
    def index(db):
        "Build or re-build the searchable records index"
        pass

    @cli.command()
    @click.argument("content")
    @click.option("-g", "--site-group", "site_group_name")
    @with_database
    def create(db, content, site_group_name=None):
        "Create a record"
        pass

    @cli.command()
    @click.argument("id")
    @click.option("-g", "--site-group", "site_group_name")
    @with_database
    def retrieve(db, id, site_group_name=None):
        "Retrieve record by ID"
        pass

    @cli.command()
    @click.argument("id")
    @click.argument("content")
    @click.option("-g", "--site-group", "site_group_name")
    @with_database
    def update(db, id, content, site_group_name=None):
        "Update a record"
        pass

    @cli.command()
    @click.argument("id")
    @click.option("-g", "--site-group", "site_group_name")
    @with_database
    def delete(db, id, site_group_name=None):
        "Mark a record as retracted"
        pass

    @cli.command()
    @click.argument("id")
    @click.option("-g", "--site-group", "site_group_name")
    @with_database
    def undelete(db, id, site_group_name=None):
        "Mark a record as unretracted"
        pass

    @cli.command()
    @click.argument("id")
    @click.argument("tag")
    @click.option("-g", "--site-group", "site_group_name")
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
    def peer():
        "Commands to manage the local OrbitDB peer"
        pass



    return cli



if __name__ == '__main__':
    build_cli()()