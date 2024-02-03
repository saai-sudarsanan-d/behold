# behold

A set of services that communicate with each other in given order, using a redis queue

```
docker build -t hyena -f DockerfileApp .
```

A master that takes care of them

```
docker build -t ringmaster -f DockerfileMaster  .
```