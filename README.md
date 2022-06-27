# crypto_otc
Cross-chain swapbot on Reddit.

One of the problems facing trustless cross-chain cross-token exchange protocols run by smart contracts is the high cost of operation. Primarily because of (1) network fees required by maintaining a fully decentralized system, and (2) Low liquidity in the dex (decentralized exchange) space.

One solution to this, especially to address problem (2) is to offer a counterparty directly network-facing for cross-token and cross-chain swaps while making immediate use of centralized exchange liquidity. Albeit this implies a centralized approach and comes at the cost of trust on behalf of the end user.

This project functions as a cross-chain over-the-counter desk for a defined list of supported crypto assets.

# Process goes as such:
User follows instructed format for creating channel by making a public reddit comment on a designated daily post. i.e. indicating seven pieces of information:
1) Amount of *Have* coin desired to be swapped
2) *Have* coin
3) *Want* coin
4) *Receive* network
5) *Receive* public address
6) *Send* network
7) *Send* public address

Supposing that the information is properly formatted and successfully recognized by the parsing function, AND that the requested networks / coins are supported, the backend opens up a channel for this transaction.

The reddit bot replies with the channel specification, i.e. Listening for *H* coin on *abc* address via the *xyz* network.

The backend system appends this to a block of open channels to be listening for, and checks for respective deposits on a perpetual time cycle.

Once a deposit is made for an active channel, the coin is automatically exchanged (direct and triangular both supported) for the requested coin and sent back to the requested receival address.

# Problems faced by this approach
Trust. The end-user has no way of verifying that the transaction will be executed to the agreement once the deposit is made, as they would via a smart contract approach. This is only absolved from a compounding trust effect of initial use. As more users utilize the bridge without problem, it increases the legitimacy, thereby increasing use, etc. etc.
