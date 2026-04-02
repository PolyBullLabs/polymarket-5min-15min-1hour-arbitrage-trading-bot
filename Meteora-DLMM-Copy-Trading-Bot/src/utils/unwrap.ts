import {
    Keypair, Connection, Transaction, ComputeBudgetProgram, sendAndConfirmTransaction
} from "@solana/web3.js";
import {
    NATIVE_MINT,
    createCloseAccountInstruction, getAssociatedTokenAddress
} from "@solana/spl-token";
import base58 from "bs58";
import { PRIVATE_KEY, RPC_ENDPOINT } from "../constants";
import { mainMenuWaiting } from "../..";

// Solana Connection and Keypair
const connection = new Connection(RPC_ENDPOINT);
const mainKp = Keypair.fromSecretKey(base58.decode(PRIVATE_KEY!));

const sleep = async (ms: number) => {
    await new Promise((resolve) => setTimeout(resolve, ms))
}

export const unwrapSol = async (mainKp: Keypair) => {
    const wSolAccount = await getAssociatedTokenAddress(NATIVE_MINT, mainKp.publicKey);
    try {
        const wsolAccountInfo = await connection.getAccountInfo(wSolAccount);
        if (wsolAccountInfo) {
            const tx = new Transaction().add(
                ComputeBudgetProgram.setComputeUnitPrice({ microLamports: 261197 }),
                ComputeBudgetProgram.setComputeUnitLimit({ units: 101337 }),
                createCloseAccountInstruction(
                    wSolAccount,
                    mainKp.publicKey,
                    mainKp.publicKey,
                ),
            );
            tx.recentBlockhash = (await connection.getLatestBlockhash()).blockhash
            tx.feePayer = mainKp.publicKey
            const sig = await sendAndConfirmTransaction(connection, tx, [mainKp], { skipPreflight: true, commitment: "confirmed" });
            console.log(`Unwrapped SOL transaction: https://solscan.io/tx/${sig}`);
            await sleep(5000);
        }
        mainMenuWaiting()
    } catch (error) {
        console.error("unwrapSol error:", error);
    }
};

// unwrapSol(mainKp)