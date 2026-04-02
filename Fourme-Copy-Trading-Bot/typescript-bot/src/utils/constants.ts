// PancakeSwap Router ABI
export const PANCAKE_ROUTER_ABI = [
  'function getAmountsOut(uint amountIn, address[] calldata path) external view returns (uint[] memory amounts)',
  'function swapExactTokensForTokens(uint amountIn, uint amountOutMin, address[] calldata path, address to, uint deadline) external returns (uint[] memory amounts)',
  'function swapExactETHForTokens(uint amountOutMin, address[] calldata path, address to, uint deadline) external payable returns (uint[] memory amounts)',
  'function swapExactTokensForETH(uint amountIn, uint amountOutMin, address[] calldata path, address to, uint deadline) external returns (uint[] memory amounts)',
  'function swapExactTokensForTokensSupportingFeeOnTransferTokens(uint amountIn, uint amountOutMin, address[] calldata path, address to, uint deadline) external returns (uint[] memory amounts)',
  'function getAmountsIn(uint amountOut, address[] calldata path) external view returns (uint[] memory amounts)',
];

// PancakeSwap Factory ABI
export const PANCAKE_FACTORY_ABI = [
  'function getPair(address tokenA, address tokenB) external view returns (address pair)',
];

// PancakeSwap Pair ABI
export const PANCAKE_PAIR_ABI = [
  'event Sync(uint112 reserve0, uint112 reserve1)',
  'event Swap(address indexed sender, uint amount0In, uint amount1In, uint amount0Out, uint amount1Out, address indexed to)',
  'function token0() external view returns (address)',
  'function token1() external view returns (address)',
  'function getReserves() external view returns (uint112 reserve0, uint112 reserve1, uint32 blockTimestampLast)',
];

// Four.meme ABI (example - adjust based on actual contract)
export const FOUR_MEME_ABI = [
  'event TokenPurchase(address indexed buyer, uint256 ethAmount, uint256 tokensReceived)',
  'event TokenSale(address indexed seller, uint256 tokensSold, uint256 ethReceived)',
  'function buyTokens() external payable',
  'function sellTokens(uint256 tokenAmount) external',
  'function calculateTokenBuy(uint256 ethAmount) external view returns (uint256)',
  'function calculateEthSell(uint256 tokenAmount) external view returns (uint256)',
];

// ERC20 ABI
export const ERC20_ABI = [
  'function balanceOf(address owner) external view returns (uint256)',
  'function transfer(address to, uint256 amount) external returns (bool)',
  'function allowance(address owner, address spender) external view returns (uint256)',
  'function approve(address spender, uint256 amount) external returns (bool)',
  'function decimals() external view returns (uint8)',
  'function symbol() external view returns (string)',
];

// WBNB address on BNB Chain
export const WBNB_ADDRESS = '0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c';

// Zero address
export const ZERO_ADDRESS = '0x0000000000000000000000000000000000000000';

// Max uint256
export const MAX_UINT256 = BigInt('0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff');

// Gas limits
export const DEFAULT_GAS_LIMIT = 300000n;
export const PANCAKE_SWAP_GAS_LIMIT = 400000n;
export const FOUR_MEME_GAS_LIMIT = 300000n;

// Transaction deadline (20 minutes)
export const TX_DEADLINE = Math.floor(Date.now() / 1000) + 60 * 20;
