import { useCallback, useEffect, useRef, useState } from "react";
import { BASE, getPassword } from "../api/client";

const ICE: RTCConfiguration = { iceServers: [{ urls: "stun:stun.l.google.com:19302" }] };

export interface CallPeer {
  id: string;
  name: string;
  stream: MediaStream | null;
}

function wsUrl(clientId: string, name: string): string {
  const url = new URL(`${BASE}/call/ws`, location.href);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.searchParams.set("client_id", clientId);
  url.searchParams.set("name", name);
  url.searchParams.set("password", getPassword());
  return url.toString();
}

/** Групповой голосовой созвон (mesh WebRTC). Сигналы идут через WebSocket бэкенда, звук — напрямую между браузерами. */
export function useCall(clientId: string, name: string) {
  const [joined, setJoined] = useState(false);
  const [muted, setMuted] = useState(false);
  const [peers, setPeers] = useState<CallPeer[]>([]);
  const [error, setError] = useState<string | null>(null);
  const ws = useRef<WebSocket | null>(null);
  const local = useRef<MediaStream | null>(null);
  const conns = useRef(new Map<string, RTCPeerConnection>());

  const upsert = (id: string, patch: Partial<CallPeer>) =>
    setPeers((list) =>
      list.some((p) => p.id === id)
        ? list.map((p) => (p.id === id ? { ...p, ...patch } : p))
        : [...list, { id, name: "Гость", stream: null, ...patch }],
    );

  const drop = (id: string) => {
    conns.current.get(id)?.close();
    conns.current.delete(id);
    setPeers((list) => list.filter((p) => p.id !== id));
  };

  const signal = (to: string, data: unknown) => ws.current?.send(JSON.stringify({ to, data }));

  const connection = (id: string): RTCPeerConnection => {
    const existing = conns.current.get(id);
    if (existing) return existing;
    const pc = new RTCPeerConnection(ICE);
    conns.current.set(id, pc);
    local.current?.getTracks().forEach((t) => pc.addTrack(t, local.current!));
    pc.onicecandidate = (e) => e.candidate && signal(id, { candidate: e.candidate });
    pc.ontrack = (e) => upsert(id, { stream: e.streams[0] });
    pc.onconnectionstatechange = () => {
      if (pc.connectionState === "failed") pc.restartIce();
    };
    return pc;
  };

  const leave = useCallback(() => {
    ws.current?.close();
    ws.current = null;
    conns.current.forEach((pc) => pc.close());
    conns.current.clear();
    local.current?.getTracks().forEach((t) => t.stop());
    local.current = null;
    setPeers([]);
    setJoined(false);
    setMuted(false);
  }, []);

  const join = async () => {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Микрофон доступен только по HTTPS (или на localhost)");
      return;
    }
    try {
      local.current = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
    } catch {
      setError("Нет доступа к микрофону");
      return;
    }
    const socket = new WebSocket(wsUrl(clientId, name));
    ws.current = socket;
    socket.onopen = () => setJoined(true);
    socket.onclose = () => {
      if (ws.current === socket) leave();
    };
    socket.onmessage = async (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "peers") {
        // Мы новичок: предлагаем соединение всем, кто уже в комнате
        for (const p of msg.peers as { id: string; name: string }[]) {
          upsert(p.id, { name: p.name });
          const pc = connection(p.id);
          await pc.setLocalDescription(await pc.createOffer());
          signal(p.id, { sdp: pc.localDescription });
        }
      } else if (msg.type === "joined") {
        upsert(msg.id, { name: msg.name });
      } else if (msg.type === "left") {
        drop(msg.id);
      } else if (msg.type === "signal") {
        const { from, data } = msg;
        const pc = connection(from);
        if (data.sdp) {
          await pc.setRemoteDescription(data.sdp);
          if (data.sdp.type === "offer") {
            await pc.setLocalDescription(await pc.createAnswer());
            signal(from, { sdp: pc.localDescription });
          }
        } else if (data.candidate) {
          await pc.addIceCandidate(data.candidate).catch(() => {});
        }
      }
    };
  };

  const toggleMute = () => {
    const next = !muted;
    local.current?.getAudioTracks().forEach((t) => (t.enabled = !next));
    setMuted(next);
  };

  useEffect(() => leave, [leave]); // уход со страницы — выходим из созвона

  return { joined, muted, peers, error, join, leave, toggleMute };
}
