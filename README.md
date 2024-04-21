# Cho phép approve pipeline khi chạy CD

- Requirement:

  Khi sử dụng CD để chạy deploy release thì mong muốn gửi thông báo về slack cho phép manager hoặc leader approved mới được chạy tiếp khi release.

- Expect:

  Có 2 option để lựa chọn approved hoặc cancel
  
  Có thể gửi về slack hoặc thực hiện tại pipeline, step quá trình chạy CD
  
  Có thể sử dụng sunCI hoặc github action hoặc etc... để thực hiện
  
  Nếu việc deploy bị lỗi hoặc failed thì cần rollback về version hiện tại


### Tạo các giá trị Repository secrets trong github để sử dụng trong file build
DOCKERHUB_ACCESS_TOKEN

DOCKERHUB_USERNAME

GIT_TOKEN

SLACK_WEBHOOK

![](https://github.com/dungnv-2032/image/assets/53817590/1d0376d9-252b-41f4-a4d4-fa8538429db3)

### Create and Setting Environments Required reviewers
- Tạo một Enviroment sẽ Required reviewers approved in pipeline.
    VD: staging

![](https://github.com/dungnv-2032/image/assets/53817590/f930613c-cb1e-4ffe-9776-b1782a5ed326)

- Config Enviroment staging vừa tạo
- Tại mục Deployment protection rules
  + Tích chọn Required reviewers
  + Add up to 5 more reviewers ( Chọn người sẽ được quyền reviewers, approved)

![](https://github.com/dungnv-2032/image/assets/53817590/e639cb9f-1ae5-4fd0-846a-9635125df572)


## Tiến hành tạo file build workflow github actions

- Tạo một file build, VD: **build.html** trong folder github của project. VD: **.github/workflows/build.yaml**


- Tạo một kịch bản workfow mong muốn. Vd như tôi tạo kịch bản flow sẽ trigger khi có pull mới merge vào branch master được closed
```
name: cd-rollback
on:
  workflow_dispatch:
  pull_request:
    branches:
      - master
    types:
      - closed
```

- Flow các jobs dự kiến sẽ tiến hành:
  + build_and_tag_image
  + send_notify_approve to Slack
  + Nếu được approved thì push image
  + Push image thành công thì tiến hành gửi send_notify_success to Slack
  + Push image failure thì tiến hành gửi send_notify_failure to Slack - check_need_rollback - nếu image đã thay đổi th tiến hành jobs rollback


- Khai báo jobs build và add tag image

Ví dụ project của tôi là **hello-cicd**

Tôi tạo thêm **latest** và tag **${{github.sha}}**

**outputs ra giá trị repo_digests** của version hiện tại, sử dụng để so sánh với repo_digests của image trong trươờng hợp push bị failure và tiến hành so sánh để kiểm tra xem image đã được apply code mới chưa

````
  build_and_tag_image:
    runs-on: ubuntu-latest
    name: build_and_tag_image
    outputs:
      repo_digests: ${{ steps.set-variable.outputs.repo_digests }}
    steps:
      - name: Login Docker Hub
        id: login_docker_hub
        uses: docker/login-action@v1
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_ACCESS_TOKEN }}
      - name: pull docker and build SHA version
        run: |
          docker pull ${{ secrets.DOCKERHUB_USERNAME }}/hello-cicd:latest
          docker tag ${{ secrets.DOCKERHUB_USERNAME }}/hello-cicd:latest ${{ secrets.DOCKERHUB_USERNAME }}/hello-cicd:${{github.sha}}
          docker push ${{ secrets.DOCKERHUB_USERNAME }}/hello-cicd:${{github.sha}}
      - name: set variable output
        id: set-variable
        shell: bash
        run: |
          repo_digests=$(docker inspect --format='{{index .RepoDigests 0}}' ${{ secrets.DOCKERHUB_USERNAME }}/hello-cicd:latest)
          echo "repo_digests=${repo_digests: -64}" >> "$GITHUB_OUTPUT"
````

- Gửi notify về slack, kèm link để mở ra pipeline approved / reject

````
  send_notify_approve:
    name: send_notify_approve
    runs-on: ubuntu-latest
    needs: build_and_tag_image
    if: success()
    steps:
      # Notify Slack with an interactive message
      - name: Send custom JSON data to Slack workflow
        id: slack
        uses: slackapi/slack-github-action@v1.25.0
        with:
          payload: |
            {
              "text": "Có một bản release cần được approve.\nENV: staging\nRepository: ${{ github.repository }}\n${{ github.event.pull_request.html_url || github.event.head_commit.url }}\n${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
            }
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK }}
          SLACK_WEBHOOK_TYPE: INCOMING_WEBHOOK
````

- Tại job push_image, khai báo environment đã Setting Environments Required reviewers ở bước trước
VD: environment: staging
Khi flow chạy đến jobs push_image sẽ yêu cầu được approved mới được chạy tiếp
````
  push_image:
    environment: staging
    name: push_image
    runs-on: ubuntu-latest
    needs: send_notify_approve
    if: success()
    steps:
      - name: Login Docker Hub
        uses: docker/login-action@v1
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_ACCESS_TOKEN }}
      - uses: actions/checkout@v2
      - name: Build and Push Docker Image
        run: |
          docker build -t ${{ secrets.DOCKERHUB_USERNAME }}/hello-cicd:latest .
          docker push ${{ secrets.DOCKERHUB_USERNAME }}/hello-cicd:latest
````

![](https://github.com/dungnv-2032/image/assets/53817590/66768495-5a90-4002-ac4b-9c80df721f28)
![](https://github.com/dungnv-2032/image/assets/53817590/348ef7ca-a38e-44f0-9aad-b6f69ffebf9a)

- Job send_notify_success thực hiện gửi Notify Success về Slack sau khi jobs push_image hoàn thành

````
  send_notify_success:
    name: send_notify_success
    runs-on: ubuntu-latest
    needs: push_image
    if: success()
    steps:
      - name: Report Status success
        id: slack_success
        uses: slackapi/slack-github-action@v1.25.0
        with:
          payload: |
            {
              "text": "Deloy finished !"
            }
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK }}
          SLACK_WEBHOOK_TYPE: INCOMING_WEBHOOK
````
![](https://github.com/dungnv-2032/image/assets/53817590/602d8851-887a-4b3b-bbb4-86a05d015505)

- Job send_notify_failure thực hiện gửi notify fail về Slack  nếu jobs push_image failure
````
  send_notify_failure:
    name: send_notify_failure
    runs-on: ubuntu-latest
    if: failure()
    needs: push_image
    steps:
      - name: Report Status fail
        id: slack_fail
        uses: slackapi/slack-github-action@v1.25.0
        with:
          payload: |
            {
              "text": "Deloy Fail !"
            }
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK }}
          SLACK_WEBHOOK_TYPE: INCOMING_WEBHOOK
````

- Job check_need_rollback thực hiện kiểm tra xem có cần Rollback lại version cũ ko
Ở đây sẽ so san giá trị repo_digests của image cũ và mới, nếu khác nhau thì chứng tỏ image đã được apply code mới bị lỗi => Thực hiện rollback
Nếu giống nhau thì image chưa được apply code mới => cancel ko cần làm
````
  check_need_rollback:
    name: check_need_rollback
    runs-on: ubuntu-latest
    outputs:
      repo_digests: ${{ steps.set-variable-latest.outputs.repo_digests }}
    needs: [send_notify_failure,build_and_tag_image]
    if: failure()
    steps:
      - name: Pull current version
        run: docker pull ${{ secrets.DOCKERHUB_USERNAME }}/hello-cicd:latest
      - name: Check repo_digests current
        id: set-variable-latest
        run: |
          repo_digests=$(docker inspect --format='{{index .RepoDigests 0}}' ${{ secrets.DOCKERHUB_USERNAME }}/hello-cicd:latest)
          echo "repo_digests=${repo_digests: -64}" >> "$GITHUB_OUTPUT"
      - name: get variable
        run: |
          echo ${{needs.build_and_tag_image.outputs.repo_digests}}
          echo ${{steps.set-variable-latest.outputs.repo_digests}}
          echo ${{needs.build_and_tag_image.outputs.repo_digests != steps.set-variable-latest.outputs.repo_digests}}
````

- Job rollback : Thực hiện push lại image cũ dựa theo image tag ${{github.sha}} đã tạo từ trớc đó
````
  rollback:
    name: rollback
    if: |
      always() && 
      (needs.build_and_tag_image.outputs.repo_digests != needs.check_need_rollback.outputs.repo_digests) &&
      contains(needs.push_image.result, 'failure')
    runs-on: ubuntu-latest
    needs: [build_and_tag_image,check_need_rollback,push_image]
    steps:
      - name: Login Docker Hub
        uses: docker/login-action@v1
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_ACCESS_TOKEN }}

      - name: Push Docker Image
        id: docker_pre_build
        run: |
          docker pull ${{ secrets.DOCKERHUB_USERNAME }}/hello-cicd:${{github.sha}}
          docker tag ${{ secrets.DOCKERHUB_USERNAME }}/hello-cicd:${{github.sha}} ${{ secrets.DOCKERHUB_USERNAME }}/hello-cicd:latest
          docker push ${{ secrets.DOCKERHUB_USERNAME }}/hello-cicd:latest
````

Flow hoạt động:

![](https://github.com/dungnv-2032/image/assets/53817590/af25d4f5-21f3-4470-b081-c7af61594308)
![](https://github.com/dungnv-2032/image/assets/53817590/4c515980-6ebb-44a6-9f30-7d47bf14f8a4)