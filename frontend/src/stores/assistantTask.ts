import { defineStore } from "pinia";

export const useAssistantTaskStore = defineStore("assistantTask", {
  state: () => ({
    running: false,
    text: "",
    progress: "",
    startedAt: 0,
    completedAt: 0,
  }),
  actions: {
    start(text: string) { this.running = true; this.text = text; this.progress = "智能体正在处理"; this.startedAt = Date.now(); this.completedAt = 0; },
    update(progress: string) { this.progress = progress; },
    finish(progress = "任务已完成") { this.running = false; this.progress = progress; this.completedAt = Date.now(); },
  },
});
