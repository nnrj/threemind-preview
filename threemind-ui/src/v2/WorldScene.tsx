import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { t } from "./i18n";
import { usePreferences } from "./preferences";
import { Button, ErrorBox } from "./ui";
import CapturePanel from "./CapturePanel";

export default function WorldScene({
  protocol,
  observation,
  selected,
  selectedGroup,
  onSelect,
}: {
  protocol: any;
  observation: any;
  selected?: string;
  selectedGroup?: string;
  onSelect?: (id: string) => void;
}) {
  const host = useRef<HTMLDivElement>(null),
    state = useRef<any>(null);
  const clicked = useRef(onSelect);
  clicked.current = onSelect;
  const prefs = usePreferences();
  const [error, setError] = useState("");
  useEffect(() => {
    if (!host.current || !protocol) return;
    const element = host.current;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch (e) {
      setError(String(e));
      return;
    }
    setError("");
    renderer.setPixelRatio(prefs.dpr);
    renderer.domElement.setAttribute("aria-label", t("物理世界三维预览"));
    element.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(
      prefs.theme === "dark" ? "#132321" : "#eaf0ec",
    );
    const camera = new THREE.PerspectiveCamera(42, 1, 0.001, 1e8);
    camera.up.set(0, 0, 1);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    scene.add(new THREE.HemisphereLight(0xffffff, 0x6b8a77, 2));
    const light = new THREE.DirectionalLight(0xffffff, 2);
    light.position.set(2, -3, 6);
    scene.add(light);
    const meshes = new Map<string, THREE.Mesh>();
    const guides = new Map<
      string,
      {
        sensor: any;
        object: THREE.CameraHelper | THREE.ArrowHelper;
        camera?: THREE.PerspectiveCamera;
      }
    >();
    for (const geom of protocol.geometries) {
      let geometry: THREE.BufferGeometry;
      const s = geom.size;
      if (geom.shape === "mesh") {
        const data = protocol.meshes?.[geom.mesh_id];
        if (!data) continue;
        geometry = new THREE.BufferGeometry();
        geometry.setAttribute(
          "position",
          new THREE.Float32BufferAttribute(data.vertices, 3),
        );
        geometry.setIndex(data.indices);
        geometry.computeVertexNormals();
      } else if (geom.shape === "ellipsoid") {
        geometry = new THREE.SphereGeometry(1, 20, 12).scale(s[0], s[1], s[2]);
      } else if (geom.shape === "box")
        geometry = new THREE.BoxGeometry(s[0] * 2, s[1] * 2, s[2] * 2);
      else if (geom.shape === "plane")
        geometry = new THREE.PlaneGeometry(s[0] * 2, s[1] * 2);
      else if (geom.shape === "capsule")
        geometry = new THREE.CapsuleGeometry(s[0], s[1] * 2, 8, 16).rotateX(
          Math.PI / 2,
        );
      else if (geom.shape === "cylinder")
        geometry = new THREE.CylinderGeometry(s[0], s[0], s[1] * 2, 24).rotateX(
          Math.PI / 2,
        );
      else geometry = new THREE.SphereGeometry(s[0], 24, 16);
      const [r, g, b, a] = geom.rgba;
      const material = new THREE.MeshStandardMaterial({
        color: new THREE.Color(r, g, b),
        opacity: a,
        transparent: a < 1,
        side: THREE.DoubleSide,
        roughness: 0.75,
        depthWrite: !geom.observer_overlay,
      });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.userData = {
        id: geom.id,
        body: geom.body_id,
        observerOverlay: !!geom.observer_overlay,
        declaredVisible: geom.visible !== false,
      };
      scene.add(mesh);
      meshes.set(geom.id, mesh);
    }
    for (const sensor of protocol.sensors) {
      if (sensor.kind === "camera_rgb") {
        const eye = new THREE.PerspectiveCamera(
          sensor.fovy,
          sensor.width / sensor.height,
          0.01,
          0.5,
        );
        const helper = new THREE.CameraHelper(eye);
        helper.visible = false;
        scene.add(helper);
        guides.set(sensor.id, { sensor, object: helper, camera: eye });
      } else if (sensor.kind === "rangefinder") {
        const helper = new THREE.ArrowHelper(
          new THREE.Vector3(0, 0, 1),
          new THREE.Vector3(),
          sensor.maximum_distance,
          0xca873e,
        );
        helper.visible = false;
        scene.add(helper);
        guides.set(sensor.id, { sensor, object: helper });
      }
    }
    let raf = 0,
      last = 0,
      disposed = false;
    function invalidate() {
      if (!raf && !disposed) raf = requestAnimationFrame(draw);
    }
    function draw(now: number) {
      raf = 0;
      if (now - last < 1000 / prefs.fps) {
        invalidate();
        return;
      }
      last = now;
      controls.update();
      renderer.render(scene, camera);
    }
    function resize() {
      const width = element.clientWidth,
        height = element.clientHeight;
      if (!width || !height) return;
      renderer.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      invalidate();
    }
    function fit() {
      const box = new THREE.Box3();
      for (const mesh of meshes.values())
        if (
          mesh.visible &&
          !mesh.userData.observerOverlay &&
          (protocol.observer_focus !== "robot" || mesh.userData.body)
        )
          box.expandByObject(mesh);
      const center = box.isEmpty()
        ? new THREE.Vector3()
        : box.getCenter(new THREE.Vector3());
      const span = Math.max(
        1,
        box.isEmpty() ? 4 : box.getSize(new THREE.Vector3()).length(),
      );
      // Fit actual geometry, excluding observer guides and lights.
      const direction = new THREE.Vector3(1, -1.3, 0.9).normalize();
      const right = new THREE.Vector3()
        .crossVectors(camera.up, direction)
        .normalize();
      const up = new THREE.Vector3().crossVectors(direction, right);
      const tanV = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
      let distance = 1;
      for (const x of [box.min.x, box.max.x])
        for (const y of [box.min.y, box.max.y])
          for (const z of [box.min.z, box.max.z]) {
            const delta = new THREE.Vector3(x, y, z).sub(center);
            distance = Math.max(
              distance,
              Math.abs(delta.dot(right)) / (tanV * camera.aspect) +
                delta.dot(direction),
              Math.abs(delta.dot(up)) / tanV + delta.dot(direction),
            );
          }
      controls.target.copy(center);
      camera.position
        .copy(center)
        .addScaledVector(direction, box.isEmpty() ? 5 : distance * 1.15);
      camera.near = Math.max(0.0001, span / 10000);
      camera.far = Math.max(100, span * 100);
      camera.updateProjectionMatrix();
      controls.update();
      invalidate();
    }
    function update(value: any) {
      for (const item of value?.geometries ?? []) {
        const mesh = meshes.get(item.id);
        if (!mesh) continue;
        // Population slots can be inactive; their physical observation owns visibility.
        mesh.visible =
          mesh.userData.declaredVisible && (item.rgba?.[3] ?? 1) > 0;
        const m = item.rotation_matrix;
        mesh.position.fromArray(item.position);
        mesh.quaternion.setFromRotationMatrix(
          new THREE.Matrix4().set(
            m[0],
            m[1],
            m[2],
            0,
            m[3],
            m[4],
            m[5],
            0,
            m[6],
            m[7],
            m[8],
            0,
            0,
            0,
            0,
            1,
          ),
        );
      }
      const bodies = new Map<string, any>(
        (value?.bodies ?? []).map((body: any) => [body.id, body]),
      );
      for (const { sensor, object, camera: eye } of guides.values()) {
        const body = bodies.get(sensor.body_id);
        object.userData.ready = !!body;
        if (!body) {
          object.visible = false;
          continue;
        }
        const [w, x, y, z] = body.quaternion;
        const rotation = new THREE.Quaternion(x, y, z, w);
        const position = new THREE.Vector3()
          .fromArray(sensor.position)
          .applyQuaternion(rotation)
          .add(new THREE.Vector3().fromArray(body.position));
        const [sw, sx, sy, sz] = sensor.quaternion;
        rotation.multiply(new THREE.Quaternion(sx, sy, sz, sw));
        if (eye) {
          eye.position.copy(position);
          eye.quaternion.copy(rotation);
          eye.updateMatrixWorld();
          (object as THREE.CameraHelper).update();
        } else {
          object.position.copy(position);
          (object as THREE.ArrowHelper).setDirection(
            new THREE.Vector3(0, 0, 1).applyQuaternion(rotation),
          );
        }
      }
      invalidate();
    }
    const ray = new THREE.Raycaster(),
      pointer = new THREE.Vector2();
    function choose(event: MouseEvent) {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.set(
        ((event.clientX - rect.left) / rect.width) * 2 - 1,
        (-(event.clientY - rect.top) / rect.height) * 2 + 1,
      );
      ray.setFromCamera(pointer, camera);
      const hit = ray.intersectObjects(
        [...meshes.values()].filter(
          (mesh) => mesh.visible && !mesh.userData.observerOverlay,
        ),
      )[0];
      if (hit) clicked.current?.(hit.object.userData.id);
    }
    state.current = { update, fit, meshes, guides, invalidate,
      capture: () => { renderer.render(scene, camera); return renderer.domElement; } };
    controls.addEventListener("change", invalidate);
    renderer.domElement.addEventListener("click", choose);
    const observer = new ResizeObserver(resize);
    observer.observe(element);
    update(observation);
    resize();
    fit();
    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      observer.disconnect();
      controls.dispose();
      renderer.domElement.removeEventListener("click", choose);
      for (const mesh of meshes.values()) {
        mesh.geometry.dispose();
        (mesh.material as THREE.Material).dispose();
      }
      for (const { object } of guides.values()) object.dispose();
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
      state.current = null;
    };
  }, [protocol, prefs.dpr, prefs.fps, prefs.theme]);
  useEffect(() => {
    state.current?.update(observation);
  }, [observation]);
  useEffect(() => {
    for (const [id, mesh] of state.current?.meshes ?? [])
      (mesh.material as THREE.MeshStandardMaterial).emissive.set(
        (selectedGroup === "geometries" && id === selected) ||
          (selectedGroup === "bodies" && mesh.userData.body === selected)
          ? "#234e41"
          : "#000000",
      );
    for (const [id, { object }] of state.current?.guides ?? [])
      object.visible =
        selectedGroup === "sensors" &&
        id === selected &&
        !!object.userData.ready;
    state.current?.invalidate();
  }, [
    selected,
    selectedGroup,
    protocol,
    observation,
    prefs.theme,
    prefs.dpr,
    prefs.fps,
  ]);
  return (
    <div className="world-scene-wrap">
      <div className="world-scene" ref={host} />
      <Button
        type="button"
        variant="small"
        onClick={() => state.current?.fit()}
      >
        {t("重置视角")}
      </Button>
      <ErrorBox error={error} />
      <CapturePanel key={protocol?.id ?? protocol?.label} disabled={!!error} source={{
        draw: () => { if (!state.current) throw new Error(t("画面尚未准备好")); return state.current.capture(); },
        metadata: () => ({ world: protocol?.label || protocol?.schema || "ThreeMind",
          time: observation?.physical_time_us == null ? t("静态世界预览") : `${t("模拟时间")} ${Number(observation.physical_time_us) / 1e6} s`,
          legend: t("实际世界观察画面；观察视角不作为感官输入。") }),
      }} />
      <p className="footnote">
        {t(
          "拖动旋转，滚轮缩放。这里是观察视角，不是虚拟眼睛；显示设置不会改变物理输入。",
        )}
      </p>
      {selectedGroup === "sensors" &&
        protocol?.sensors?.some(
          (sensor: any) =>
            sensor.id === selected &&
            ["camera_rgb", "rangefinder"].includes(sensor.kind),
        ) && (
          <p className="footnote">
            {t(
              "辅助线表示声明的感官方向；相机视锥长度仅供观察，测距箭头表示量程，不是实际命中结果。",
            )}
          </p>
        )}
    </div>
  );
}
