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

App key -> Site key -> personal key -> record key

reading a record:

Site read subkey -> record public key

where "->" is a signing relationship?


```
@peermodel
class Sample:
    collection_date: datetime

    runs: List[aggregated(Run)]
    assemblies: List[aggregated(Assemblies)]

@peermodel
class EnvironmentalSample(Sample):
    collection_location: Location

@peermodel
class ClinicalSample(Sample):
    host: Species

@peermodel(stuff=True, more_stuff="stuff")
class Isolate:


    names: List[Indexed(str)]
    sample: Union[EnvironmentalSample, ClinicalSample]
    runs: List[aggregated(Run)]
    assemblies: List[aggregated(Assemblies)]

@peerevent()
class SomethingHappened:

    isolate: Isolate



```

Developing with peermodel

Use cookiecutter on the peermodel-cookiecutter
Your application's model should be a dependency
Release on Pypi




Updating your peermodel