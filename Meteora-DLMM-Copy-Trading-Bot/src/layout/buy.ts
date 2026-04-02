import { ComputeBudgetProgram, Keypair, LAMPORTS_PER_SOL, PublicKey, sendAndConfirmTransaction, SystemProgram, Transaction, TransactionInstruction, TransactionMessage, VersionedTransaction } from "@solana/web3.js";
import { readSettings, sleep } from "../utils/utils";
import { HIGHER_MC_INTERVAL, HIGHER_TP_INTERVAL, LOWER_MC_INTERVAL, LOWER_TP_INTERVAL, PRIVATE_KEY, PUMP_SWAP_PROGRAM_ID, SELL_TIMER, solanaConnection, STOP_LOSS } from "../constants";
import base58 from "bs58";
import { logger, wrapSol } from "../utils";
import { closeAccount, createAssociatedTokenAccountIdempotentInstruction, createCloseAccountInstruction, getAssociatedTokenAddress, getOrCreateAssociatedTokenAccount, NATIVE_MINT, TOKEN_PROGRAM_ID } from "@solana/spl-token";
import { mainMenuWaiting } from "../..";
import { PumpAmmSdk } from "@pump-fun/pump-swap-sdk";
import { Direction } from "../types"; // Ensure Direction is imported as an enum
import BN from "bn.js";

export const mainKp = Keypair.fromSecretKey(base58.decode(PRIVATE_KEY!))

export const buy_monitor_autosell = async () => {
    const pSwap = new PumpAmmSdk(solanaConnection);
    const data = readSettings();
    const BUY_AMOUNT = Number(data.amount); // Convert to lamports
    const TOKEN_CA = new PublicKey(data.mint!);
    const IS_PUMPFUN = data.isPump!;
    const SLIPPAGE = Number(data.slippage);

    let settings = {
        mint: new PublicKey(data.mint!),
        poolId: new PublicKey(data.poolId!),
        isPump: data.isPump!,
        amount: Number(data.amount),
        slippage: Number(data.slippage)
    }

    const POOL_ID = settings.poolId;
    const solBalance = (await solanaConnection.getBalance(mainKp.publicKey)) / LAMPORTS_PER_SOL;

    const baseAta = await getAssociatedTokenAddress(TOKEN_CA, POOL_ID, true);;
    const quoteAta = await getAssociatedTokenAddress(NATIVE_MINT, POOL_ID, true);

    if (solBalance < Number(BUY_AMOUNT)) {
        logger.error(`There is not enough balance in your wallet. Please deposit some more solana to continue.`)
        return
    }
    logger.info(`Pumpswap Trading bot is running`)
    logger.info(`Wallet address: ${mainKp.publicKey.toBase58()}`)
    logger.info(`Balance of the main wallet: ${solBalance}Sol`)

    // await wrapSol(mainKp, Number(BUY_AMOUNT) * 2)

    let middleMC = await getTokenMC(quoteAta, baseAta, IS_PUMPFUN, settings.mint)
    let mc = Math.floor(middleMC)
    let lowerMC = mc * (1 - LOWER_MC_INTERVAL / 100)
    let higherMC = mc * (1 + HIGHER_MC_INTERVAL / 100)
    const mcCheckInterval = 200
    let mcChecked = 0
    let bought = false
    let processingToken = false

    logger.info(`Starting MarketCap monitoring, initial MC is ${middleMC}Sol ...`)

    while (1) {

        let changedSolBalance: number | null = 0;

        let tpInterval
        processingToken = true

        while (1) {
            if (mcChecked != 0) {
                middleMC = await getTokenMC(quoteAta, baseAta, IS_PUMPFUN, settings.mint)
                // middleHolderNum = (await findHolders(mintStr)).size
            }
            if (mcChecked > 100000) {
                bought = false
                processingToken = false
                break;
            }
            if (middleMC < 35) {
                bought = false
                processingToken = false
                break;
            }

            logger.info(`Current MC: ${middleMC}Sol, LMC: ${lowerMC}Sol, HMC: ${higherMC}Sol`)

            if (middleMC < lowerMC) {
                logger.info(`Market Cap keep decreasing now, reached ${lowerMC}Sol, keep monitoring...`)
                mc = Math.floor(middleMC)
                lowerMC = mc * (1 - LOWER_MC_INTERVAL / 100)
                higherMC = mc * (1 + HIGHER_MC_INTERVAL / 100)
            } 

            await sleep(mcCheckInterval)
            mcChecked++

        }

        if (bought) {
            mcChecked = 0
            if (middleMC > 1000) tpInterval = 1
            else tpInterval = 1
            // Waiting for the AssociatedTokenAccount is confirmed
            const maxRetries = 50
            const delayBetweenRetries = 1000
            const ata = await getAssociatedTokenAddress(TOKEN_CA, mainKp.publicKey)

            for (let attempt = 0; attempt < maxRetries; attempt++) {
                try {
                    const tokenAmount = Number((await solanaConnection.getTokenAccountBalance(ata)).value.amount);

                    // Monitoring pnl
                    attempt = maxRetries
                    const amountIn = tokenAmount

                    try {

                        logger.info("Showing pnl monitoring...")
                        const priceCheckInterval = 200
                        const timesToCheck = SELL_TIMER / priceCheckInterval
                        let TP_LEVEL = 1.3
                        let higherTP = TP_LEVEL
                        let lowerTP = TP_LEVEL - LOWER_TP_INTERVAL

                        const SolOnSl = Number((BUY_AMOUNT * (100 - STOP_LOSS) / 100).toFixed(6))
                        let timesChecked = 0
                        let tpReached = false
                        do {

                            try {
                                // Quote to Base swap (⬇️)
                                const amountOut = Number(await pSwap.swapAutocompleteQuoteFromBase(
                                    POOL_ID,
                                    new BN(amountIn),
                                    0,
                                    "baseToQuote",
                                ));

                                changedSolBalance = (await solanaConnection.getBalance(mainKp.publicKey)) / LAMPORTS_PER_SOL;
                                console.log("🚀 ~ constbuy_monitor_autosell= ~ amountOut:", amountOut / 10 ** 9)

                                console.log("🚀 ~ constbuy_monitor_autosell= ~ solBalance:", solBalance)
                                console.log("🚀 ~ constbuy_monitor_autosell= ~ changedSolBalance:", changedSolBalance)
                                console.log("🚀 ~ constbuy_monitor_autosell= ~ wrapSolBalance! - changedWrapSolBalance!:", solBalance! - changedSolBalance!)
                                const pnl = (Number(amountOut / 10 ** 9) - (solBalance! - changedSolBalance!)) / (solBalance! - changedSolBalance!) * 100
                                console.log("🚀 ~ constbuy_monitor_autosell= ~ pnl:", pnl)

                                if (pnl > TP_LEVEL && !tpReached) {
                                    tpReached = true
                                    logger.info(`PNL is reached to the lowest Profit level ${TP_LEVEL}%`)
                                }

                                if (pnl > 0)
                                    if (pnl > higherTP) {
                                        // TP_LEVEL = Math.floor(pnl / (tpInterval / 2)) * (tpInterval / 2)
                                        TP_LEVEL = pnl

                                        logger.info(`Token price goes up and up, so raising take profit from ${lowerTP + tpInterval / 2}% to ${TP_LEVEL}%`)

                                        higherTP = TP_LEVEL + HIGHER_TP_INTERVAL
                                        lowerTP = TP_LEVEL - LOWER_TP_INTERVAL
                                    } else if (pnl < lowerTP && tpReached) {
                                        logger.fatal("Token is on profit level, price starts going down, selling tokens...")
                                        try {
                                            await swap(pSwap, POOL_ID, TOKEN_CA, new BN(tokenAmount), SLIPPAGE, mainKp, "quoteToBase");
                                            break;
                                        } catch (err) {
                                            logger.info("Fail to sell tokens ...")
                                        }
                                    }

                            } catch (e) {
                                // logger.error(e)
                            } finally {
                                timesChecked++
                            }
                            await sleep(priceCheckInterval)
                            if (timesChecked >= timesToCheck) {
                                await swap(pSwap, POOL_ID, TOKEN_CA, new BN(tokenAmount), SLIPPAGE, mainKp, "quoteToBase");
                                break
                            }
                        } while (1)

                        logger.warn(`New pumpswap token ${TOKEN_CA.toBase58()} PNL processing finished once and continue monitoring MarketCap`)
                        // logger.info(`Waiting 5 seconds for new buying and selling...`)
                        await sleep(2000)

                    } catch (error) {
                        logger.error("Error when setting profit amounts", error)
                        mainMenuWaiting()
                    }

                    // break; // Break the loop if fetching the account was successful
                } catch (error) {
                    if (error instanceof Error && error.name === 'TokenAccountNotFoundError') {
                        logger.info(`Attempt ${attempt + 1}/${maxRetries}: Associated token account not found, retrying...`);
                        if (attempt === maxRetries - 1) {
                            logger.error(`Max retries reached. Failed to fetch the token account.`);
                            mainMenuWaiting()
                        }
                        // Wait before retrying
                        await new Promise((resolve) => setTimeout(resolve, delayBetweenRetries));
                    } else if (error instanceof Error) {
                        // logger.error(`Unexpected error while fetching token account: ${error.message}`);
                        // throw error;
                        logger.info(`Attempt ${attempt + 1}/${maxRetries}: Associated token account not found, retrying...`);
                        if (attempt === maxRetries - 1) {
                            logger.error(`Max retries reached. Failed to fetch the token account.`);
                            mainMenuWaiting()
                        }
                        await new Promise((resolve) => setTimeout(resolve, delayBetweenRetries));

                    } else {
                        logger.error(`An unknown error occurred: ${String(error)}`);
                        throw error;
                    }
                }
            }
        }

        if (!processingToken) {
            mainMenuWaiting()
            break;
        }

    }
}

export const swap = async (pSwap: PumpAmmSdk, pool: PublicKey, mint: PublicKey, buyAmount: BN, slippage: number, user: Keypair, direction: Direction) => {
    console.log("🚀 ~ swap ~ buyAmount:", buyAmount)
    const baseAta = await getAssociatedTokenAddress(mint, user.publicKey);
    try {

        const buyTx = new Transaction();

        buyTx.add(
            createAssociatedTokenAccountIdempotentInstruction(user.publicKey, baseAta, user.publicKey, mint),
        );

       //swapInstructions
        
        buyTx.add(...swapInstructions);

        buyTx.feePayer = user.publicKey;
        buyTx.recentBlockhash = (await solanaConnection.getLatestBlockhash()).blockhash
        buyTx.lastValidBlockHeight = (await solanaConnection.getLatestBlockhash()).lastValidBlockHeight;

        try {
            const simulationResult = await solanaConnection.simulateTransaction(buyTx);
            const { value } = simulationResult;
            console.log("🚀 ~ buy ~ value:", value)
            if (value.err) {
                logger.error("Simulation failed:", value.err);
            } else {
                logger.info("Simulation successful:", value.logs);
            }
        } catch (error: any) {
            throw new Error(`Transaction simulation failed: ${error.message}`)
        }

        const createSig = await sendAndConfirmTransaction(solanaConnection, buyTx, [user]);
        console.log("Create BondingCurve Sig : ", `https://solscan.io/tx/${createSig}`);
    } catch (error) {
        console.log("error => ", error)
    }
}

const getTokenPrice = async (quoteVault: PublicKey, baseVault: PublicKey, isPump: Boolean) => {
    const quoteBal = (await solanaConnection.getTokenAccountBalance(quoteVault)).value.uiAmount
    const baseBal = (await solanaConnection.getTokenAccountBalance(baseVault)).value.uiAmount

    let price: number = 0

    price = quoteBal! / baseBal!
    console.log("price of the token: ", price)
    return price
}

const getTokenMC = async (quoteVault: PublicKey, baseVault: PublicKey, isPump: Boolean, mint: PublicKey) => {
    const currentPrice = await getTokenPrice(quoteVault, baseVault, isPump)
    const totalSupply = (await solanaConnection.getTokenSupply(mint)).value.uiAmount
    return currentPrice * totalSupply!
}
