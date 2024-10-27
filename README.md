# peermodel

## A secure capabilities peer-to-peer ORM built on OrbitDB.

---

## Installation

`pip install peermodel`
## Usage

`$ prmdl --help`


---
Created from Binfie-cookiecutter, https://github.com/crashfrog/binfie-cookiecutter


## Notes

A user can create or join a "ring." A majority of the members of the ring must approve a new member.

Records created by a member of a ring are owned by the ring. You can specify which ring owns the record, otherwise your default ring is used.

A member of the ring can extend guest access to the ring's records. A guest has read-only access to the ring's records.

A member of the ring can make a record public; read-only by everyone.

A user can request guest access or membership in a ring. A ring member can approve guest access; a majority of ring members can approve membership.

Credential management:
    Mac Keychain via keyring
    Windows Credential Locker via keyring
    https://pypi.org/project/keyring/
    https://pypi.org/project/keyrings.osx-keychain-keys/


    Linux stuff (secretservice, KDE Wallet)
    Federal badges: PIV, CAC

    Password / credential managers w/ Python support
    1Password https://pypi.org/project/1password/
    BitWarden https://github.com/corpusops/bitwardentools

## CLI Usage
```
$ prmdl --help
Usage: prmdl [OPTIONS] COMMAND [ARGS]...

  Management interface for PeerModel identity and rings.

Options:
  --help  Show this message and exit.

Commands:
  init  Initialize your identity
  ring  Commands for managing rings

$ prmdl init --help
Usage: prmdl init [OPTIONS]

  Initialize your identity

Options:
  --help  Show this message and exit.

$ prmdl ring --help
Usage: prmdl ring [OPTIONS] COMMAND [ARGS]...

  Commands for managing rings

Options:
  --help  Show this message and exit.

Commands:
  approve     Approve membership or guest access request
  create      Initalize keys for a new ring for an existing application
  invite      Invite new user into the ring
  list        List rings you're a member of
  regenerate  Regenerate ring keys
  review      Review existing access requests
  revoke      Revoke ring group access and regenerate keys


```



## Example


```
peer = peermodel.App("My Distributed App's Datamodel")


@peer.model
class Sample:
    collection_date: datetime

    runs: List[aggregated(Run)]
    assemblies: List[aggregated(Assemblies)]

@peer.model
class EnvironmentalSample(Sample):
    collection_location: Location

@peer.model
class ClinicalSample(Sample):
    host: Species

@peer.model(stuff=True, more_stuff="stuff")
class Isolate:


    names: List[Indexed(str)]
    sample: Union[EnvironmentalSample, ClinicalSample]
    runs: List[aggregated(Run)]
    assemblies: List[aggregated(Assemblies)]

@peer.event
class SomethingHappened:

    isolate: Isolate

@peer.event
class AnotherEvent:

    message: str
    about: Isolate


@SomethingHappened.whenHappen()
def somethingDidHappen(event):
    AnotherEvent.throw(message="it happened", about=event.isolate)


```

Developing with peermodel

Use cookiecutter on the peermodel-cookiecutter
Your application's model should be a dependency
Release on Pypi




Updating your peermodel