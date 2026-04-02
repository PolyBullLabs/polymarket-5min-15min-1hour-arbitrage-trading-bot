import { createAssociatedTokenAccountIdempotentInstruction, createSyncNativeInstruction, getAssociatedTokenAddress, NATIVE_MINT, TOKEN_PROGRAM_ID } from "@solana/spl-token";
import { ComputeBudgetProgram, Connection, Keypair, sendAndConfirmTransaction, SystemProgram, Transaction } from "@solana/web3.js";
import bs58 from 'bs58'
import { PRIVATE_KEY, RPC_ENDPOINT, solanaConnection } from "../constants";
import { mainMenuWaiting } from "../..";
import { readSettings } from ".";

/**
 * Wraps the given amount of SOL into WSOL.
 * @param {Keypair} mainKp - The central keypair which holds SOL.
 * @param {number} wsolAmount - The amount of SOL to wrap.
 */

const sleep = async (ms: number) => {
    await new Promise((resolve) => setTimeout(resolve, ms))
}

export const wrapSol = async (mainKp: Keypair, amount: number) => {
    console.log(`It is wrapping ${amount}Sol to Wsol now.`)

    const maxRetries = 20
    let attempt = 0

    do {

        try {
            const wSolAccount = await getAssociatedTokenAddress(NATIVE_MINT, mainKp.publicKey);
            const tx = new Transaction().add(
                ComputeBudgetProgram.setComputeUnitPrice({ microLamports: 1_000_197 }),
                ComputeBudgetProgram.setComputeUnitLimit({ units: 51_337 }),
            );
            if (!await solanaConnection.getAccountInfo(wSolAccount))
                tx.add(
                    createAssociatedTokenAccountIdempotentInstruction(
                        mainKp.publicKey,
                        wSolAccount,
                        mainKp.publicKey,
                        NATIVE_MINT,
                    ),
                )

            tx.add(
                SystemProgram.transfer({
                    fromPubkey: mainKp.publicKey,
                    toPubkey: wSolAccount,
                    lamports: Math.floor(amount * 10 ** 9),
                }),
                createSyncNativeInstruction(wSolAccount, TOKEN_PROGRAM_ID),
            )


            tx.recentBlockhash = (await solanaConnection.getLatestBlockhash()).blockhash
            tx.feePayer = mainKp.publicKey
            // console.log("Wrap simulation: ", await connection.simulateTransaction(tx))
            const sig = await sendAndConfirmTransaction(solanaConnection, tx, [mainKp], { skipPreflight: true, commitment: "confirmed" });
            if (sig) {
                console.log(`Wrapped SOL transaction: https://solscan.io/tx/${sig}`);
                mainMenuWaiting()
                return
            }

            await sleep(5000);
        } catch (error) {
            console.error("Failed to wrap Sol, so retrying...");
            attempt++
        }
    } while (attempt < maxRetries)

    mainMenuWaiting()

    // })

};