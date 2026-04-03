import { z } from "zod";

export const birthInputSchema = z.object({
  fullName: z.string().min(2),
  birthDate: z.string().min(8),
  birthTime: z.string().min(4),
  birthLocation: z.string().min(2),
});

export const calculateRequestSchema = z.object({
  input: birthInputSchema,
});

export const readingRequestSchema = z.object({
  chartId: z.uuid(),
  chartData: z.record(z.string(), z.unknown()),
  userName: z.string().min(2),
});

export const chatMessageSchema = z.object({
  role: z.enum(["system", "user", "assistant"]),
  content: z.string().min(1),
});

export const chatRequestSchema = z.object({
  chartId: z.uuid(),
  messages: z.array(chatMessageSchema).min(1),
  chartData: z.record(z.string(), z.unknown()),
  userName: z.string().min(2),
});
