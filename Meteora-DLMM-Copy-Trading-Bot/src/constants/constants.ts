import { Connection, PublicKey } from "@solana/web3.js"
import dotenv from 'dotenv';

dotenv.config();

export const PRIVATE_KEY = process.env.PRIVATE_KEY
export const RPC_ENDPOINT = process.env.RPC_ENDPOINT!
export const RPC_WEBSOCKET_ENDPOINT = process.env.RPC_WEBSOCKET_ENDPOINT
export const solanaConnection = new Connection(RPC_ENDPOINT, "confirmed")
