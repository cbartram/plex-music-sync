# Plex Sync

A tool which sync's a spotify song, album, or playlist to a plex media server.

## Plex Server Deployment

The plex server can be deployed via the helm chart with: 

`helm install plex ./manifests/plex -n plex`

To upgrade the chart if it's modified use:

`helm upgrade plex ./manifests/plex -f ./manifests/plex/values.yaml -n plex`

## Claim Code

Within the plex server there is a claim code which needs to be refreshed when the server goes offline. The code expires
in 5 minutes and is stored as a kubernetes secret.  Head to [https://plex.tv/claim](https://plex.tv/claim) and login to generate a new code. 

`kubectl create secret generic plex-secrets --from-literal=PLEX_CLAIM=<YOUR_CLAIM_CODE> -n plex`

You can rollout the deployment to use the new secret with: 

`kubectl rollout restart deployment plex-server -n plex`

### Updating the Claim Code

To update the secret value with the new claim code use:

```shell
kubectl patch secret plex-config -n plex \
  --type merge \
  -p '{"stringData":{"PLEX_CLAIM":"YOUR-NEW-CODE-HERE"}}'

kubectl rollout restart deployment plex-server -n plex
```

## Running the tests

`pytest`

## Built With

- [Python](https://go.dev/doc/install) - Programming Language

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code
of conduct, and the process for submitting pull requests to us.

## Versioning

We use [Semantic Versioning](http://semver.org/) for versioning. For the versions
available, see the [tags on this
repository](https://github.com/cbartram/kraken-loader-plugin/tags).

## Authors

- **C. Bartram** - *Initial Project implementation* - [cbartram](https://github.com/cbartram)

See also the list of
[contributors](https://github.com/PurpleBooth/a-good-readme-template/contributors)
who participated in this project.

## License

This project is licensed under the [CC0 1.0 Universal](LICENSE.md)
Creative Commons License - see the [LICENSE.md](LICENSE.md) file for
details

