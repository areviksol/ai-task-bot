
import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";


export function useTaskEvents(enabled: boolean) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!enabled) return;

    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout>;
    let stopped = false;



    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";

    const wsUrl = `${wsProtocol}//${window.location.host}`;

    function connect() {
      if (stopped) return;

      socket = new WebSocket(`${wsUrl}/ws/tasks`);

      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);

          if (
            message.type === "connected" ||
            message.type === "tasks.changed"
          ) {
            queryClient.invalidateQueries({
              queryKey: ["tasks"],
            });
          }
        } catch {
          // Ignore malformed notifications.
        }
      };

      socket.onclose = (event) => {
        if (stopped) return;

        // Policy violation: likely an invalid session.
        if (event.code === 1008) return;

        reconnectTimer = setTimeout(connect, 3000);
      };
    }

    connect();

    return () => {
      stopped = true;
      clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [enabled, queryClient]);
}
