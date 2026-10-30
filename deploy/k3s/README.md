# odysseus k3s 배포 (odysseus.delvrio.com, namespace `odysseus`)

이 폴더와 `.gitea/workflows/ci.yml`, `.github/workflows/sync-to-gitea.yml` 은 포크(hyungjin7/odysseus)에만 더한 파일이다.
upstream 코드는 고치지 않으므로 GitHub "Sync fork" 로 upstream 을 따라가도 충돌하지 않는다.
`docker-compose.yml` 을 kompose 로 바꾸지 않고 손으로 옮긴 이유는 아래 "compose 와 다른 점"에 있다.

## 흐름

GitHub `dev`(이 포크의 기본 브랜치) push → `Sync to Gitea` → Gitea `hyungjin7/odysseus` main
→ Gitea CI: 이미지 `gitea.delvrio.com/hyungjin7/odysseus/app:<sha>` 빌드 → `kubectl apply` + `set image -n odysseus`.

원본 따라가기: `.github/workflows/sync-upstream.yml` 이 매주 일요일 12:00(KST) 원본 `odysseus-dev/odysseus` dev 를
이 포크 dev 로 합치고 `Sync to Gitea` 를 실행한다(= 매주 자동 업데이트·재배포). 원본이 워크플로 파일을 바꾼 주에도
가져오려면 Actions 시크릿 `UPSTREAM_SYNC_TOKEN`(repo·workflow 권한 PAT)을 넣는다. 수동 실행은 Actions › Sync upstream › Run workflow.

## 구성

| 이름 | 하는 일 | 저장 |
| --- | --- | --- |
| odysseus | 본체(FastAPI, :7000) | nfs-hdd `odysseus-data` 120Gi (`/app/data`, `.ssh`, `.cache/huggingface`, `.local`), 로그는 emptyDir |
| chromadb | 벡터 DB(:8000) | nfs-hdd `chromadb-data` 10Gi |
| searxng | 웹 검색(:8080) | emptyDir(기동마다 설정 재생성) |
| ntfy | 알림(:80, 선택) | emptyDir |

저장 규칙: 영구 데이터는 nfs-hdd(예상치의 2배 이상), 휘발성 데이터는 노드 로컬(emptyDir).

## 처음 한 번 할 일

1. **DNS**: `odysseus.delvrio.com` 을 `bbb.delvrio.com` 과 같은 곳으로 등록한다(인증서는 cert-manager 가 발급).
2. **Gitea 저장소**: Gitea 에 빈 저장소 `hyungjin7/odysseus` 를 만들고 Actions 를 켠다.
3. **GitHub Actions 시크릿**(이 포크): `GITEA_USER`, `GITEA_TOKEN`. upstream 워크플로(ci, docker-publish 등)는 필요 없으면 Actions 화면에서 끈다.
4. **Secret**(클러스터에 직접, 커밋하지 않음):
   ```bash
   kubectl create namespace odysseus --dry-run=client -o yaml | kubectl apply -f -
   kubectl create secret generic odysseus-secret -n odysseus \
     --from-literal=ODYSSEUS_ADMIN_PASSWORD='<관리자 비밀번호>' \
     --from-literal=SEARXNG_SECRET="$(openssl rand -base64 48)"
   ```
   다른 키는 `secrets.example.yaml` 참고. Secret 을 바꾼 뒤에는 `kubectl rollout restart deploy/odysseus deploy/searxng -n odysseus`.
5. **공통 로그인**: bbb 저장소의 `odysseus-auth-ingress.yaml`·navigation_apps `odysseus` 행이 배포돼 있어야 한다.
   사용할 사람은 bbb Admin › 그룹에 `odysseus` 그룹을 만들고 넣는다(superuser 는 항상 통과).

## LLM 연결 (LM Studio)

- 주소 `http://studio.delvrio.com:1234/v1`(OpenAI 호환). Pod 에서는 `hostAliases` 로 112.150.97.248 에 붙는다(bbb 서비스와 같음).
- API 키는 저장소·ConfigMap 에 넣지 않는다. 첫 로그인 후 odysseus 설정 화면의 모델 엔드포인트에
  위 주소와 LM Studio 키를 넣는다(앱 DB 에 저장). 기본 모델 `gemma-4-e4b-it-mlx@8bit`, 대체 `google/gemma-4-12b`.

## compose 와 다른 점(kompose 결과에서 고친 것)

- PVC 크기·`storageClassName: nfs-hdd` 지정(kompose 는 100Mi·클래스 없음).
- `ALLOWED_ORIGINS`·`OAUTH_REDIRECT_BASE_URL` 을 실제 도메인으로, `SECURE_COOKIES=true`, `LOCALHOST_BYPASS=false`.
- `enableServiceLinks: false` — `chromadb` Service 가 `CHROMADB_PORT=tcp://…` 를 주입하면 본체가 죽는다(`int()` 실패).
- `depends_on`(searxng healthy) 대신 initContainer 로 searxng 를 기다린다.
- `host.docker.internal`·호스트 docker 소켓은 쓰지 않는다.
- Ingress + 공통 로그인(forwardAuth), NetworkPolicy(본체가 사설 IP 대역으로 못 나가게) 추가.

## 주의

- SQLite(`/app/data/app.db`)라 본체는 **replica 1 + Recreate** 다. 늘리지 않는다.
  NFS 잠금 문제("database is locked")가 보이면 prod-pg 로 옮긴다(`DATABASE_URL=postgresql://…`).
- entrypoint 가 root 로 `/app/data` 소유권을 맞춘 뒤 uid 1000 으로 내려간다. NFS 가 root_squash 면 chown 이 실패해 쓰기 오류가 날 수 있다.
- Cookbook(컨테이너 안 로컬 모델 설치·llama.cpp 빌드)은 CPU·디스크를 많이 쓴다. LM Studio 를 쓰므로 켜지 않는다.

## 확인

```bash
kubectl get pods,pvc,ingress -n odysseus
kubectl logs deploy/odysseus -n odysseus | grep -i password   # Secret 없이 띄웠을 때 첫 관리자 비밀번호
```
