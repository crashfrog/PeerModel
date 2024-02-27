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

Record:
    UUID
    model-package-name
    model-package-version
    Read-key Fingerprint (for indexing)
    Read-key encrypted Record Public Key
    Master-key encrypted Record Private Key
    Record Private-key encrypted record

PeerFile:
    IPFS Hash
    Symmetric-encrypted bytes

Library key -> Site key -> Site + App key -> personal app keys -> record key

Keysystem -> read key, write key, signing key, encrypt key?

The PeerModel (pm) library has a master keysystem

A PeerModel data model library has a list of keysystems based on minor version revisions, 

A pm user has personal keys, at least one in different storage mechanisms (as below)

A pm site group has a keysystem, locked by the user's personal keys

A pm site group has guests who receive a read key signed by the site group key and the app key

Ephemeral shared keys
https://pypi.org/project/shamirs/
https://www.ewsn.org/file-repository/ewsn2020/174_175_park.pdf

reading a record:

Site read subkey -> record public key

where "->" is a signing relationship?

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


IPLD


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