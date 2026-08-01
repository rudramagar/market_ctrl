# How to use
```sh
./backend_start.sh --log-level DEBUG
```

# How to forward port (qaServer --> sharedServer --> WindowsWorkSpace)
1. On SharedServer
```sh
ssh -N -T -o ExitOnForwardFailure=yes -L 127.0.0.1:8080:127.0.0.1:8080 xnt-dde1qa01
```

2. Forward to windows using putty

## Access api endpoint from terminal or browser
```sh
curl -s http://127.0.0.1:18080/health | jq
```
