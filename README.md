# 봉구 · Bonggu 3D

소중한 반려견 봉구를 닮은 그림 스타일의 3D 모델입니다. macOS·Windows 데스크톱 펫에 사용할
Blender 원본, GLB, 리그와 동작을 담고 있습니다. 데스크톱 앱 자체는 아직 포함하지 않습니다.

![승인된 봉구의 정적 외형](release/bonggu-v2-preview.png)

## 사용할 파일

| 목적 | 파일 |
|---|---|
| 최신 동작 모델 · 앱 연결 | [bonggu-v2-everyday.glb](locomotion/bonggu-v2-everyday.glb) |
| 최신 동작 편집 | [bonggu-v2-everyday.blend](locomotion/bonggu-v2-everyday.blend) |
| 새 동작을 만들 중립 리그 | [bonggu-v2-tail-rig.blend](locomotion/bonggu-v2-tail-rig.blend) |
| 승인된 고화질 정적 원본 | [bonggu-v2-master.blend](release/bonggu-v2-master.blend) · [GLB](release/bonggu-v2-master.glb) |
| 정적 경량 모델 | [bonggu-v2-desktop.glb](release/bonggu-v2-desktop.glb) |
| 그림 설계도 | [references/](references/) |

최신 GLB는 약 8.4MiB, 36,968 삼각형, 78개 스킨 관절이며 `Smile` 표정과 18개 동작을 포함합니다.
Blender 편집 리그는 조작·보조 본을 포함해 112개 본입니다. 텍스처는 파일에 내장되어 있습니다.
고화질 정적 원본은 505,204 삼각형과 4K 텍스처를 보존합니다.

[기본 동작 영상](locomotion/everyday-preview.mp4) · [목 움직임](locomotion/neck-movements.mp4) ·
[꼬리 움직임](locomotion/tail-movements.mp4) · [앉기](locomotion/sit-sequence.mp4) ·
[엎드리기](locomotion/lie-sequence.mp4)

## 재생과 편집

Blender에서 최신 동작 파일을 열고 NLA Editor에서 재생할 트랙 하나만 켭니다.
기본 선택은 `Idle`입니다. 스트립을 선택하고 Tab으로 Tweak Mode에 들어가 편집할 수 있습니다.
새 포즈는 중립 리그에서 `Bonggu.Rig`를 선택해 Pose Mode로 작업합니다.

| 조작점 | 역할 |
|---|---|
| `CTRL.Root`, `CTRL.Body` | 전체 이동·회전, 몸 높이·기울기 |
| `CTRL.ForePaw.L/R`, `CTRL.HindPaw.L/R` | 앞발·뒷발 위치 |
| `CTRL.Carpus.L/R`, `CTRL.Hock.L/R` | X 회전으로 손목·뒷발목 접기 |
| `CTRL.*ToeRoll.L/R` | X 양의 회전으로 발끝 밀어내기 |
| `CTRL.Look` | X: 숙이기·올려보기, Y: 좌우 보기, Z: 갸웃하기 |
| `CTRL.NeckBase` | 목 아래쪽 움직임 |
| `Pelvis`, `Spine.01`–`Spine.04`, `Chest` | 골반·허리·가슴 움직임 |
| `Ear.*`, `Tail.01`–`Tail.08` | 귀·꼬리 움직임 |

Armature의 `IK=1`은 발 조작점, `IK=0`은 다리 FK입니다. 자동 IK/FK 포즈 맞춤은 없습니다.
`Smile=0..1`로 입을 닫은 상태에서 웃는 표정까지 조절합니다. 목의 `MCH.*` 보조 본은 직접 조작하지 않습니다.

앱 연결 시 동작 이름·길이·루프 여부·상태·이동 속도는 [clips.json](locomotion/clips.json)을 사용합니다.
걷기와 달리기는 제자리 동작이라 앱에서 위치를 이동해야 합니다. 앉기, 엎드리기, 꼬리 내리기는
각각 진입 → 대기 → 복귀 순서로 연결합니다. 꼬리 동작은 전신 클립이며 걷기에 바로 더하는 레이어는 아닙니다.

[animations/](animations/)의 앞발 긁기·냄새 찾기·하울링은 **이전 골격의 별도 팩**입니다.
최신 18개 클립에 통합하지 않았으며 소리는 포함하지 않습니다. 몸통의 큰 굽힘, 달리기의 다양한 보법,
극단적인 관절 자세와 실제 데스크톱 앱의 성능은 추가 작업 대상입니다.

## 재생성·검증

Blender 5.2.2 LTS 기준입니다. `blender` 실행 파일을 PATH에 추가한 뒤 저장소 루트에서 실행합니다.
이 단계는 기존 결과물을 덮어쓰므로 수동 편집본은 먼저 별도로 보존하세요.

```sh
blender -b --python-exit-code 1 --python locomotion/build-locomotion.py
blender -b --python-exit-code 1 --python locomotion/verify-locomotion.py
```

중립 리그까지 재생성할 때는 `locomotion/prepare-tail-rig.py`를 먼저 실행합니다.
더 앞 단계의 편집 소스는 `expressions/smile/refined/`, `rigged/`, `rigged/anatomy/`에 있습니다.
고화질 정적 모델은 완성된 원본으로 제공하며 Meshy 생성 과정은 이 저장소의 재생성 범위에 포함하지 않습니다.

미리보기는 `locomotion/render-previews.py`를 Blender로 실행한 뒤, Python 3·Pillow·FFmpeg가 있는
환경에서 `python3 locomotion/package-previews.py`로 인코딩합니다. FFmpeg와 FFprobe는 PATH에서 찾습니다.
한글 폰트는 macOS/Windows 기본 폰트를 사용하거나 `BONGGU_FONT`에 폰트 경로를 지정합니다.
임시 렌더 프레임은 Git에서 제외됩니다.

에이전트 작업 지침은 [AGENTS.md](AGENTS.md)와 [CLAUDE.md](CLAUDE.md)에 있습니다.
